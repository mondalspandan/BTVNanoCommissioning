from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone
from glob import glob

try:
    from rich import box
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, TextColumn
    from rich.table import Table
    from rich.text import Text
    from rich.console import Group

    RICH_AVAILABLE = True
except ImportError:
    box = None
    Console = object
    Live = None
    Panel = None
    Progress = None
    Table = None
    Text = None
    Group = None
    RICH_AVAILABLE = False

STATUS_FILENAME = "job_status.json"
ICONS = {
    "ok": "✅",
    "warn": "⚠️",
    "error": "❌",
    "info": "ℹ️",
    "submit": "🚀",
    "check": "🔎",
    "resubmit": "🔁",
    "hadd": "📦",
    "done": "🎉",
    "clock": "🕒",
}
CONDOR_EVENT_RE = re.compile(r"^(\d{3}) \((\d+)\.(\d+)\.\d+\)")
CONDOR_CLUSTER_RE = re.compile(r"(?:job|hadd)\.(?:log|out|err)_(\d+)(?:-\d+)?$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _status_path(job_dir: str) -> str:
    return os.path.join(job_dir, STATUS_FILENAME)


def _stage_entry(stage: str, summary: str = "", detail: str = "") -> dict:
    return {
        "stage": stage,
        "summary": summary,
        "detail": detail,
        "timestamp": _now_iso(),
    }


def _default_status(job_dir: str, job_name: str = "", output_dir: str = "") -> dict:
    return {
        "job_dir": os.path.abspath(job_dir) if job_dir else "",
        "job_name": job_name or os.path.basename(os.path.abspath(job_dir)) if job_dir else "",
        "output_dir": os.path.abspath(output_dir) if output_dir else "",
        "created_at": "",
        "updated_at": "",
        "submitted_jobs": None,
        "checked_outputs": {
            "status": "",
            "missing_outputs": None,
            "checked_jobs": None,
            "job_ids": [],
        },
        "resubmitted_jobs": {
            "count": None,
            "job_ids": [],
            "pending_reset": False,
        },
        "hadd_jobs_submitted": None,
        "hadd_jobs_checked": {
            "status": "",
            "failed": None,
            "checked_jobs": None,
        },
        "all_done": False,
        "stages_passed": [],
    }


def _merge_status(data: dict, job_dir: str) -> dict:
    base = _default_status(job_dir)
    if not isinstance(data, dict):
        return base
    for key, value in base.items():
        if key not in data:
            data[key] = value
    if not isinstance(data.get("checked_outputs"), dict):
        data["checked_outputs"] = base["checked_outputs"]
    else:
        for key, value in base["checked_outputs"].items():
            data["checked_outputs"].setdefault(key, value)
    if not isinstance(data.get("resubmitted_jobs"), dict):
        data["resubmitted_jobs"] = base["resubmitted_jobs"]
    else:
        for key, value in base["resubmitted_jobs"].items():
            data["resubmitted_jobs"].setdefault(key, value)
    if not isinstance(data.get("hadd_jobs_checked"), dict):
        data["hadd_jobs_checked"] = base["hadd_jobs_checked"]
    else:
        for key, value in base["hadd_jobs_checked"].items():
            data["hadd_jobs_checked"].setdefault(key, value)
    if not isinstance(data.get("stages_passed"), list):
        data["stages_passed"] = []
    return data


def load_status(job_dir: str, create: bool = True) -> dict:
    path = _status_path(job_dir)
    if os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
        except json.JSONDecodeError:
            return _default_status(job_dir)
        data = _merge_status(data, job_dir)
        return data
    if not create:
        return _default_status(job_dir)
    data = _default_status(job_dir)
    save_status(job_dir, data)
    return data


def save_status(job_dir: str, data: dict) -> None:
    data["job_dir"] = os.path.abspath(job_dir)
    data["updated_at"] = _now_iso()
    os.makedirs(job_dir, exist_ok=True)
    path = _status_path(job_dir)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=4, sort_keys=False)
    os.replace(tmp_path, path)


def ensure_status(job_dir: str, job_name: str = "", output_dir: str = "") -> dict:
    data = load_status(job_dir, create=True)
    if job_name and not data.get("job_name"):
        data["job_name"] = job_name
    if output_dir and not data.get("output_dir"):
        data["output_dir"] = os.path.abspath(output_dir)
    if not data.get("created_at"):
        data["created_at"] = _now_iso()
    save_status(job_dir, data)
    return data


def _append_stage(data: dict, stage: str, summary: str = "", detail: str = "") -> None:
    data.setdefault("stages_passed", [])
    data["stages_passed"].append(_stage_entry(stage, summary=summary, detail=detail))


def record_submission(job_dir: str, total_jobs: int, job_name: str = "", output_dir: str = "") -> dict:
    data = ensure_status(job_dir, job_name=job_name, output_dir=output_dir)
    data["submitted_jobs"] = int(total_jobs)
    _append_stage(data, "Submitted", f"{total_jobs} jobs", "")
    save_status(job_dir, data)
    return data


def record_checked_outputs(
    job_dir: str,
    checked_jobs: int,
    missing_jobs: int,
    job_ids: list | None = None,
) -> dict:
    data = load_status(job_dir)
    data["checked_outputs"] = {
        "status": "All jobs done" if missing_jobs == 0 else f"{missing_jobs} outputs missing",
        "missing_outputs": int(missing_jobs),
        "checked_jobs": int(checked_jobs),
        "job_ids": list(job_ids or []),
    }
    data["resubmitted_jobs"] = {
        "count": None,
        "job_ids": [],
        "pending_reset": False,
    }
    if missing_jobs == 0:
        _append_stage(data, "Checked outputs", "All jobs done", f"{checked_jobs} jobs checked")
    else:
        _append_stage(
            data,
            "Checked outputs",
            f"{missing_jobs} outputs missing",
            f"{checked_jobs} jobs checked",
        )
    save_status(job_dir, data)
    return data


def record_resubmitted_jobs(job_dir: str, job_ids: list) -> dict:
    data = load_status(job_dir)
    count = len(job_ids)
    data["resubmitted_jobs"] = {
        "count": count,
        "job_ids": [str(job_id) for job_id in job_ids],
        "pending_reset": True,
    }
    _append_stage(data, "Jobs resubmitted", f"{count} jobs resubmitted", "")
    save_status(job_dir, data)
    return data


def record_hadd_submitted(job_dir: str, n_jobs: int) -> dict:
    data = load_status(job_dir)
    data["hadd_jobs_submitted"] = int(n_jobs)
    _append_stage(data, "Hadd jobs submitted", f"{n_jobs} jobs submitted", "")
    save_status(job_dir, data)
    return data


def record_hadd_checked(job_dir: str, checked_jobs: int, failed_jobs: int) -> dict:
    data = load_status(job_dir)
    data["hadd_jobs_checked"] = {
        "status": "All done" if failed_jobs == 0 else f"{failed_jobs} failed",
        "failed": int(failed_jobs),
        "checked_jobs": int(checked_jobs),
    }
    if failed_jobs == 0:
        data["all_done"] = True
        _append_stage(
            data,
            "Hadd jobs checked",
            "All done",
            f"{checked_jobs} jobs checked",
        )
        _append_stage(data, "All done", "All done", "")
    else:
        data["all_done"] = False
        _append_stage(
            data,
            "Hadd jobs checked",
            f"{failed_jobs} failed",
            f"{checked_jobs} jobs checked",
        )
    save_status(job_dir, data)
    return data


def find_job_dir_by_output(output_dir: str, search_root: str | None = None) -> str | None:
    target = os.path.abspath(output_dir)
    module_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    roots = [search_root] if search_root else [os.getcwd(), module_root]
    roots = [r for r in roots if r]
    for root in roots:
        for job_dir in sorted(
            glob(os.path.join(root, "jobs_*")) + glob(os.path.join(root, "job_*"))
        ):
            args_path = os.path.join(job_dir, "arguments.json")
            if not os.path.isfile(args_path):
                continue
            try:
                with open(args_path) as f:
                    args = json.load(f)
            except Exception:
                continue
            if os.path.abspath(str(args.get("outputDir", ""))) == target:
                return job_dir
    return None


def _job_dirs(root: str) -> list[str]:
    dirs = []
    module_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    search_roots = [root, module_root] if root else [module_root]
    for search_root in search_roots:
        for pattern in ("jobs_*", "job_*"):
            dirs.extend(glob(os.path.join(search_root, pattern)))
    return sorted({os.path.abspath(d) for d in dirs if os.path.isdir(d)})


def _fmt_value(value, default=""):
    if value is None:
        return default
    return str(value)


def _state_icon(state: str) -> str:
    return {
        "done": ICONS["ok"],
        "warn": ICONS["warn"],
        "error": ICONS["error"],
        "info": ICONS["info"],
    }.get(state, ICONS["info"])


def _state_style(state: str) -> str:
    return {
        "done": "bold green",
        "warn": "bold yellow",
        "error": "bold red",
        "info": "bold cyan",
    }.get(state, "bold cyan")


def _job_overall_state(data: dict) -> str:
    if data.get("all_done"):
        return "done"
    if data.get("hadd_jobs_submitted") is not None:
        return "warn"
    if data.get("checked_outputs", {}).get("missing_outputs") not in (None, 0):
        return "warn"
    if data.get("submitted_jobs") is not None:
        return "info"
    return "info"


def _job_title(data: dict) -> str:
    name = data.get("job_name") or os.path.basename(data.get("job_dir", "")) or "job"
    if str(name).startswith("jobs_"):
        name = str(name)[5:]
    return str(name)


def _job_stage_label(stage: str) -> tuple[str, str]:
    mapping = {
        "Submitted": (ICONS["submit"], "green"),
        "Checked outputs": (ICONS["check"], "cyan"),
        "Jobs resubmitted": (ICONS["resubmit"], "yellow"),
        "Hadd jobs submitted": (ICONS["hadd"], "magenta"),
        "Hadd jobs checked": (ICONS["hadd"], "blue"),
        "All done": (ICONS["done"], "green"),
    }
    return mapping.get(stage, (ICONS["info"], "white"))


def _stage_summary(data: dict) -> str:
    pieces = []
    submitted = data.get("submitted_jobs")
    if submitted is not None:
        pieces.append(f"{ICONS['submit']} Submitted {submitted}")
    checked = data.get("checked_outputs", {})
    if checked.get("status"):
        pieces.append(f"{ICONS['check']} Checked: {checked['status']}")
    resubmitted = data.get("resubmitted_jobs", {})
    if resubmitted.get("count"):
        pieces.append(f"{ICONS['resubmit']} Resubmitted {resubmitted['count']}")
    hadd_sub = data.get("hadd_jobs_submitted")
    if hadd_sub is not None:
        pieces.append(f"{ICONS['hadd']} Hadd submitted {hadd_sub}")
    hadd_checked = data.get("hadd_jobs_checked", {})
    if hadd_checked.get("status"):
        pieces.append(f"{ICONS['hadd']} Hadd checked: {hadd_checked['status']}")
    if data.get("all_done"):
        pieces.append(f"{ICONS['done']} All done")
    return f" {ICONS['clock']} " + "  →  ".join(pieces) if pieces else f"{ICONS['clock']} No status yet"


def _latest_condor_cluster(log_dir: str, prefix: str = "job") -> int | None:
    if not os.path.isdir(log_dir):
        return None
    clusters = []
    for path in glob(os.path.join(log_dir, f"{prefix}.*_*")):
        match = CONDOR_CLUSTER_RE.search(os.path.basename(path))
        if match:
            clusters.append(int(match.group(1)))
    return max(clusters) if clusters else None


def read_condor_status(
    job_dir: str,
    data: dict | None = None,
    *,
    prefix: str = "job",
    log_subdir: str = "log",
    unavailable_label: str = "unsubmitted",
) -> dict:
    log_dir = os.path.join(job_dir, log_subdir)
    cluster = _latest_condor_cluster(log_dir, prefix=prefix)
    if cluster is None:
        return {
            "state": "unsubmitted",
            "label": unavailable_label,
            "detail": "logs unavailable",
            "cluster": None,
            "done": None,
            "total": None,
        }

    log_path = os.path.join(log_dir, f"{prefix}.log_{cluster}")
    if not os.path.isfile(log_path):
        return {
            "state": "unsubmitted",
            "label": unavailable_label,
            "detail": f"{prefix}.log_{cluster} unavailable",
            "cluster": cluster,
            "done": None,
            "total": None,
        }

    submitted = set()
    terminated = set()
    held = set()
    removed = set()
    try:
        with open(log_path, errors="replace") as f:
            for line in f:
                match = CONDOR_EVENT_RE.match(line)
                if not match:
                    continue
                event, event_cluster, proc = match.groups()
                if int(event_cluster) != cluster:
                    continue
                if event == "000":
                    submitted.add(proc)
                elif event == "005":
                    terminated.add(proc)
                elif event == "012":
                    held.add(proc)
                elif event == "009":
                    removed.add(proc)
    except OSError as exc:
        return {
            "state": "error",
            "label": "status unavailable",
            "detail": str(exc),
            "cluster": cluster,
            "done": None,
            "total": None,
        }

    total = len(submitted)
    if total == 0:
        return {
            "state": "unsubmitted",
            "label": unavailable_label,
            "detail": f"{prefix}.log_{cluster} has no submit events",
            "cluster": cluster,
            "done": None,
            "total": None,
        }

    done = len(terminated)
    state = "done" if done >= total else "warn" if held or removed else "running"
    job_kind = "jobs"
    if prefix == "hadd":
        job_kind = "hadd jobs"
    elif data:
        resubmitted = data.get("resubmitted_jobs", {})
        resubmitted_count = resubmitted.get("count")
        submitted_jobs = data.get("submitted_jobs")
        if (
            (resubmitted_count and int(resubmitted_count) == total)
            or (isinstance(submitted_jobs, int) and total < submitted_jobs)
        ):
            job_kind = "resubmission jobs"
    extras = []
    if held:
        extras.append(f"{len(held)} held")
    if removed:
        extras.append(f"{len(removed)} removed")
    detail = f"cluster {cluster}"
    if extras:
        detail += f" ({', '.join(extras)})"
    return {
        "state": state,
        "label": f"{done}/{total} {job_kind} done",
        "job_kind": job_kind,
        "detail": detail,
        "cluster": cluster,
        "done": done,
        "total": total,
    }


def read_hadd_condor_status(job_dir: str) -> dict:
    return read_condor_status(
        job_dir,
        prefix="hadd",
        log_subdir=os.path.join("haddscripts", "hadd_logs"),
        unavailable_label="Unavailable",
    )


def _condor_status_text(status: dict | None) -> Text:
    if status is None:
        return Text(f"{ICONS['clock']} checking...", style="dim cyan")
    state = status.get("state")
    style = {
        "done": "bold green",
        "running": "bold cyan",
        "warn": "bold yellow",
        "unsubmitted": "dim",
        "error": "bold red",
    }.get(state, "cyan")
    icon = {
        "done": ICONS["ok"],
        "running": ICONS["clock"],
        "warn": ICONS["warn"],
        "unsubmitted": ICONS["info"],
        "error": ICONS["error"],
    }.get(state, ICONS["info"])
    done = status.get("done")
    total = status.get("total")
    job_kind = status.get("job_kind")
    if isinstance(done, int) and isinstance(total, int) and job_kind:
        text = Text(f"{icon} {done}/{total} done", style=style)
        if job_kind != "jobs":
            text.append(f"\n{job_kind}", style=style)
    else:
        text = Text(f"{icon} {status.get('label', 'checking...')}", style=style)
    detail = status.get("detail")
    if detail:
        text.append(f"\n{detail}", style="dim")
    return text


def _condor_progress(status: dict | None) -> Progress | None:
    if not RICH_AVAILABLE or status is None:
        return None
    done = status.get("done")
    total = status.get("total")
    if not isinstance(done, int) or not isinstance(total, int) or total <= 0:
        return None
    complete_style = "green" if done >= total else "cyan"
    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=14, complete_style=complete_style, finished_style="green"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        expand=False,
    )
    progress.add_task("", total=total, completed=min(done, total))
    return progress


def _compact_condor_text(status: dict | None, label: str = "Condor") -> Text:
    if status is None:
        return Text(f"{ICONS['clock']} {label}: checking...", style="dim cyan")
    state = status.get("state")
    style = {
        "done": "bold green",
        "running": "bold cyan",
        "warn": "bold yellow",
        "unsubmitted": "dim",
        "error": "bold red",
    }.get(state, "cyan")
    icon = {
        "done": ICONS["ok"],
        "running": ICONS["clock"],
        "warn": ICONS["warn"],
        "unsubmitted": ICONS["info"],
        "error": ICONS["error"],
    }.get(state, ICONS["info"])
    done = status.get("done")
    total = status.get("total")
    job_kind = status.get("job_kind")
    if isinstance(done, int) and isinstance(total, int):
        suffix = ""
        if job_kind and job_kind not in ("jobs", "hadd jobs"):
            suffix = f" {job_kind.replace(' jobs', '')}"
        return Text(f"{icon} {label}: {done}/{total}{suffix}", style=style)
    return Text(f"{icon} {label}: {status.get('label', 'checking...')}", style=style)


def _processing_cell(data: dict, condor: dict | None):
    checked = data.get("checked_outputs", {})
    submitted = _fmt_value(data.get("submitted_jobs"), "-")
    checked_status = checked.get("status") or "-"
    checked_style = "green" if checked_status == "All jobs done" else "yellow" if checked_status != "-" else "cyan"
    lines = [
        Text(f"{ICONS['submit']} Submitted: {submitted}", style="green"),
        _compact_condor_text(condor, "Condor"),
    ]
    progress = _condor_progress(condor)
    if progress:
        lines.append(progress)
    lines.append(Text(f"{ICONS['check']} Outputs: {checked_status}", style=checked_style))
    resub = data.get("resubmitted_jobs", {})
    if resub.get("count"):
        lines.append(Text(f"{ICONS['resubmit']} Resubmitted: {resub['count']}", style="yellow"))
    return Group(*lines)


def _hadd_cell(data: dict, hadd_condor: dict | None):
    hadd = data.get("hadd_jobs_checked", {})
    hadd_submitted = _fmt_value(data.get("hadd_jobs_submitted"), "-")
    hadd_checked = hadd.get("status") or "-"
    hadd_style = "green" if data.get("all_done") else "yellow" if data.get("hadd_jobs_submitted") is not None else "cyan"
    lines = [
        Text(f"{ICONS['hadd']} Submitted: {hadd_submitted}", style=hadd_style),
        _compact_condor_text(hadd_condor, "Condor"),
    ]
    progress = _condor_progress(hadd_condor)
    if progress:
        lines.append(progress)
    lines.append(Text(f"{ICONS['check']} Checked: {hadd_checked}", style=hadd_style))
    return Group(*lines)


def _compact_status(status: dict | None, unavailable: str = "-") -> str:
    if status is None:
        return "checking"
    done = status.get("done")
    total = status.get("total")
    if isinstance(done, int) and isinstance(total, int):
        label = f"{done}/{total}"
        job_kind = status.get("job_kind")
        if job_kind and job_kind not in ("jobs", "hadd jobs"):
            label += " resub"
        return label
    label = str(status.get("label") or unavailable)
    return "n/a" if label == "Unavailable" else label


def _short_status(value: str) -> str:
    return {
        "All jobs done": "done",
        "All done": "done",
        "Unavailable": "n/a",
        "unsubmitted": "unsubmitted",
    }.get(value, value)


def _compact_processing_value(data: dict, condor: dict | None) -> str:
    checked = data.get("checked_outputs", {})
    pieces = [
        f"sub {_fmt_value(data.get('submitted_jobs'), '-')}",
        f"cond {_compact_status(condor)}",
        f"out {_short_status(checked.get('status') or '-')}",
    ]
    resub = data.get("resubmitted_jobs", {})
    if resub.get("count"):
        pieces.append(f"resub {resub['count']}")
    return " | ".join(pieces)


def _compact_hadd_value(data: dict, hadd_condor: dict | None) -> str:
    hadd = data.get("hadd_jobs_checked", {})
    return " | ".join(
        [
            f"sub {_fmt_value(data.get('hadd_jobs_submitted'), '-')}",
            f"cond {_compact_status(hadd_condor, unavailable='Unavailable')}",
            f"check {_short_status(hadd.get('status') or '-')}",
        ]
    )


def _build_detailed_table(rows: list[tuple[str, dict]], condor_known: dict, hadd_condor_known: dict):
    table = Table(box=box.SIMPLE_HEAVY, expand=True, show_lines=True)
    table.add_column("Job", style="bold", ratio=1, min_width=10, max_width=20)
    table.add_column("State", justify="center", ratio=1, max_width=13)
    table.add_column("Processing", ratio=2, min_width=22, max_width=28, no_wrap=False)
    table.add_column("Hadd", ratio=2, min_width=20, no_wrap=False)
    table.add_column("Timeline", ratio=3, no_wrap=False)

    for job_dir, data in rows:
        condor = condor_known.get(job_dir)
        hadd_condor = hadd_condor_known.get(job_dir)
        overall_state = _job_overall_state(data)
        overall_label = (
            f"{_state_icon(overall_state)} "
            + ("All done" if data.get("all_done") else "In progress")
        )
        table.add_row(
            Text(_job_title(data), style="bold white"),
            Text(overall_label, style=_state_style(overall_state)),
            _processing_cell(data, condor),
            _hadd_cell(data, hadd_condor),
            Text(_stage_summary(data), style="white"),
        )
    return table


def _build_compact_table(
    rows: list[tuple[str, dict]],
    condor_known: dict,
    hadd_condor_known: dict,
    title: str | None = None,
):
    table = Table(
        title=title,
        box=box.SIMPLE,
        expand=True,
        show_lines=False,
        header_style="bold cyan",
    )
    table.add_column("Job", style="bold", min_width=10, max_width=24)
    table.add_column("State", max_width=12)
    table.add_column("Processing", ratio=3, no_wrap=True, overflow="ellipsis")
    table.add_column("Hadd", ratio=2, no_wrap=True, overflow="ellipsis")

    for job_dir, data in rows:
        overall_state = _job_overall_state(data)
        state_label = "done" if data.get("all_done") else "active"
        table.add_row(
            Text(_job_title(data), style="bold white"),
            Text(f"{_state_icon(overall_state)} {state_label}", style=_state_style(overall_state)),
            Text(_compact_processing_value(data, condor_known.get(job_dir)), style="white"),
            Text(_compact_hadd_value(data, hadd_condor_known.get(job_dir)), style="white"),
        )
    return table


def _stage_history_line(stages: Counter):
    if not stages:
        return None
    text = Text(f"{ICONS['info']} Stage history  ", style="bold cyan", no_wrap=True, overflow="ellipsis")
    for idx, (stage, count) in enumerate(stages.most_common()):
        if idx:
            text.append("  •  ", style="dim")
        icon, color = _job_stage_label(stage)
        text.append(f"{icon} {stage}: {count}", style=color)
    return text


def _stage_label(stage: str, status: str) -> Text:
    label = Text(stage)
    if status == "done":
        label.stylize("bold green")
    elif status == "warn":
        label.stylize("bold yellow")
    elif status == "error":
        label.stylize("bold red")
    else:
        label.stylize("bold cyan")
    return label


def _progress_badge(label: str, value: str, state: str = "info", rich_markup: bool = True) -> str:
    icon = _state_icon(state)
    if rich_markup and RICH_AVAILABLE:
        return f"[{_state_style(state)}]{icon} {label}:[/] {value}"
    return f"{icon} {label}: {value}"


def build_dashboard(
    root: str = ".",
    condor_statuses: dict[str, dict] | None = None,
    hadd_condor_statuses: dict[str, dict] | None = None,
    terminal_height: int | None = None,
):
    job_dirs = _job_dirs(root)
    if not job_dirs:
        if RICH_AVAILABLE:
            return Panel.fit("[bold yellow]No job directories found.[/]", title="Dashboard")
        return "No job directories found."

    statuses = []
    for job_dir in job_dirs:
        data = load_status(job_dir)
        statuses.append((job_dir, data))

    total = len(statuses)
    submitted = sum(1 for _, data in statuses if data.get("submitted_jobs") is not None)
    checked_done = sum(
        1
        for _, data in statuses
        if data.get("checked_outputs", {}).get("status") == "All jobs done"
    )
    resubmitted_pending = sum(
        1 for _, data in statuses if data.get("resubmitted_jobs", {}).get("count")
    )
    hadd_submitted = sum(
        1 for _, data in statuses if data.get("hadd_jobs_submitted") is not None
    )
    all_done = sum(1 for _, data in statuses if data.get("all_done"))
    condor_known = condor_statuses or {}
    hadd_condor_known = hadd_condor_statuses or {}
    condor_done = sum(
        1
        for job_dir, _ in statuses
        if condor_known.get(job_dir, {}).get("state") == "done"
    )
    condor_running = sum(
        1
        for job_dir, _ in statuses
        if condor_known.get(job_dir, {}).get("state") in ("running", "warn")
    )
    condor_unsubmitted = sum(
        1
        for job_dir, _ in statuses
        if condor_known.get(job_dir, {}).get("state") == "unsubmitted"
    )
    hadd_condor_done = sum(
        1
        for job_dir, _ in statuses
        if hadd_condor_known.get(job_dir, {}).get("state") == "done"
    )
    hadd_condor_running = sum(
        1
        for job_dir, _ in statuses
        if hadd_condor_known.get(job_dir, {}).get("state") in ("running", "warn")
    )
    stages = Counter()
    for _, data in statuses:
        for entry in data.get("stages_passed", []):
            if isinstance(entry, dict) and entry.get("stage"):
                stages[entry["stage"]] += 1

    if not RICH_AVAILABLE:
        lines = [f"{ICONS['info']} Condor Dashboard"]
        lines.append(
            f"{ICONS['submit']} Submitted: {submitted}/{total}   "
            f"{ICONS['check']} Checked done: {checked_done}   "
            f"{ICONS['resubmit']} Resubmitted: {resubmitted_pending}   "
            f"{ICONS['hadd']} Hadd submitted: {hadd_submitted}   "
            f"{ICONS['done']} All done: {all_done}"
        )
        for job_dir, data in statuses:
            condor = condor_known.get(job_dir)
            hadd_condor = hadd_condor_known.get(job_dir)
            condor_value = condor.get("label") if condor else "checking..."
            hadd_condor_value = hadd_condor.get("label") if hadd_condor else "checking..."
            overall_state = _job_overall_state(data)
            checked = data.get("checked_outputs", {})
            hadd = data.get("hadd_jobs_checked", {})
            lines.append(f"{_state_icon(overall_state)} {_job_title(data)}")
            lines.append(
                f"  {_progress_badge('Submitted', _fmt_value(data.get('submitted_jobs'), '-'), 'done' if data.get('submitted_jobs') is not None else 'info', rich_markup=False)}"
            )
            lines.append(
                f"  {_progress_badge('Condor', condor_value, condor.get('state', 'info') if condor else 'info', rich_markup=False)}"
            )
            lines.append(
                f"  {_progress_badge('Hadd Condor', hadd_condor_value, hadd_condor.get('state', 'info') if hadd_condor else 'info', rich_markup=False)}"
            )
            lines.append(
                f"  {_progress_badge('Outputs', checked.get('status') or '-', 'done' if checked.get('status') == 'All jobs done' else 'warn' if checked.get('status') else 'info', rich_markup=False)}"
            )
            hadd_value = f"{_fmt_value(data.get('hadd_jobs_submitted'), '-')} | {hadd.get('status') or '-'}"
            hadd_state = (
                "done"
                if data.get("all_done")
                else "warn"
                if data.get("hadd_jobs_submitted") is not None
                else "info"
            )
            lines.append(
                f"  {_progress_badge('Hadd', hadd_value, hadd_state, rich_markup=False)}"
            )
            lines.append(f"  Timeline: {_stage_summary(data)}")
        if stages:
            pieces = []
            for stage, count in stages.most_common():
                icon, _ = _job_stage_label(stage)
                pieces.append(f"{icon} {stage}: {count}")
            lines.append(f"{ICONS['info']} Stage history: " + "  |  ".join(pieces))
        return "\n".join(lines)

    header_text = Text()
    header_text.append(f"{ICONS['info']} Condor Dashboard\n", style="bold white")
    header_text.append(
        f"{ICONS['submit']} Submitted: {submitted}/{total}   ", style="green"
    )
    header_text.append(f"{ICONS['check']} Checked done: {checked_done}   ", style="cyan")
    header_text.append(
        f"{ICONS['resubmit']} Resubmitted: {resubmitted_pending}   ", style="yellow"
    )
    header_text.append(f"{ICONS['hadd']} Hadd submitted: {hadd_submitted}   ", style="magenta")
    header_text.append(f"{ICONS['done']} All done: {all_done}\n", style="bold green")
    header_text.append(
        f"{ICONS['clock']} Condor live: {condor_done} complete, {condor_running} running, {condor_unsubmitted} unsubmitted/logless",
        style="cyan",
    )
    header_text.append(
        f"   {ICONS['hadd']} Hadd condor: {hadd_condor_done} complete, {hadd_condor_running} running",
        style="magenta",
    )

    renderables = [
        Panel(
            header_text,
            title="Condor Dashboard",
            subtitle=f"Updated {_now_iso()}",
            border_style="cyan",
            box=box.ROUNDED,
        ),
    ]

    height = terminal_height or 32
    available_rows = max(8, height - 11)
    detailed_rows = 6
    compact_rows = 1
    active_statuses = [(job_dir, data) for job_dir, data in statuses if not data.get("all_done")]
    done_statuses = [(job_dir, data) for job_dir, data in statuses if data.get("all_done")]
    detail_estimate = len(statuses) * detailed_rows
    mixed_estimate = len(done_statuses) * compact_rows + len(active_statuses) * detailed_rows + 4

    if detail_estimate <= available_rows:
        renderables.append(_build_detailed_table(statuses, condor_known, hadd_condor_known))
    elif active_statuses and mixed_estimate <= available_rows:
        if done_statuses:
            renderables.append(
                _build_compact_table(
                    done_statuses,
                    condor_known,
                    hadd_condor_known,
                    title=f"{ICONS['done']} Done jobs ({len(done_statuses)})",
                )
            )
        renderables.append(_build_detailed_table(active_statuses, condor_known, hadd_condor_known))
    else:
        renderables.append(
            _build_compact_table(
                statuses,
                condor_known,
                hadd_condor_known,
                title=f"{ICONS['info']} Jobs ({len(statuses)} compact rows)",
            )
        )

    stage_line = _stage_history_line(stages)
    if stage_line:
        renderables.append(stage_line)
    return Group(*renderables)


def render_dashboard(
    root: str = ".",
    console: Console | None = None,
    condor_statuses: dict[str, dict] | None = None,
    hadd_condor_statuses: dict[str, dict] | None = None,
) -> None:
    console = console or Console() if RICH_AVAILABLE else None
    terminal_height = console.size.height if RICH_AVAILABLE and console else None
    dashboard = build_dashboard(
        root,
        condor_statuses=condor_statuses,
        hadd_condor_statuses=hadd_condor_statuses,
        terminal_height=terminal_height,
    )
    if RICH_AVAILABLE:
        console.print(dashboard)
    else:
        print(dashboard)


def watch_dashboard(root: str = ".", interval: float = 10.0) -> None:
    if not RICH_AVAILABLE:
        render_dashboard(root)
        return

    console = Console()
    job_dirs = _job_dirs(root)
    condor_statuses: dict[str, dict] = {}
    hadd_condor_statuses: dict[str, dict] = {}
    pending: dict[tuple[str, str], concurrent.futures.Future] = {}
    max_workers = max(1, min(8, (len(job_dirs) or 1) * 2))

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        next_refresh = 0.0
        with Live(
            build_dashboard(
                root,
                condor_statuses,
                hadd_condor_statuses,
                terminal_height=console.size.height,
            ),
            console=console,
            refresh_per_second=4,
            transient=False,
        ) as live:
            try:
                while True:
                    now = time.monotonic()
                    job_dirs = _job_dirs(root)
                    if now >= next_refresh:
                        for job_dir in job_dirs:
                            data = load_status(job_dir, create=False)
                            job_key = ("job", job_dir)
                            hadd_key = ("hadd", job_dir)
                            if job_key not in pending:
                                pending[job_key] = executor.submit(
                                    read_condor_status, job_dir, data
                                )
                            if hadd_key not in pending:
                                pending[hadd_key] = executor.submit(
                                    read_hadd_condor_status, job_dir
                                )
                        next_refresh = now + interval

                    for key, future in list(pending.items()):
                        if not future.done():
                            continue
                        kind, job_dir = key
                        try:
                            if kind == "hadd":
                                hadd_condor_statuses[job_dir] = future.result()
                            else:
                                condor_statuses[job_dir] = future.result()
                        except Exception as exc:
                            status = {
                                "state": "error",
                                "label": "status unavailable",
                                "detail": str(exc),
                                "cluster": None,
                                "done": None,
                                "total": None,
                            }
                            if kind == "hadd":
                                hadd_condor_statuses[job_dir] = status
                            else:
                                condor_statuses[job_dir] = status
                        del pending[key]

                    live.update(
                        build_dashboard(
                            root,
                            condor_statuses,
                            hadd_condor_statuses,
                            terminal_height=console.size.height,
                        )
                    )
                    time.sleep(0.25)
            except KeyboardInterrupt:
                pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Display condor job status dashboard")
    parser.add_argument(
        "--root",
        default=".",
        help="Directory to scan for job directories (default: current directory)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=10.0,
        help="Seconds between condor log refreshes in live mode (default: %(default)s)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Render once and exit instead of opening the live dashboard",
    )
    args = parser.parse_args()
    if args.once:
        job_dirs = _job_dirs(args.root)
        condor_statuses = {
            job_dir: read_condor_status(job_dir, load_status(job_dir, create=False))
            for job_dir in job_dirs
        }
        hadd_condor_statuses = {
            job_dir: read_hadd_condor_status(job_dir) for job_dir in job_dirs
        }
        render_dashboard(
            args.root,
            condor_statuses=condor_statuses,
            hadd_condor_statuses=hadd_condor_statuses,
        )
    else:
        watch_dashboard(args.root, interval=args.interval)


if __name__ == "__main__":
    main()
