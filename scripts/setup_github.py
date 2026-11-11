"""Legt Labels, Meilensteine und Arbeitspakete (Issues mit Sub-Issues) im GitHub-Repo an.

Aufruf:  python3 scripts/setup_github.py OWNER/REPO
Braucht: GitHub CLI (gh), eingeloggt. Bereits vorhandene Einträge werden übersprungen.
"""
import json
import subprocess
import sys
from pathlib import Path


def gh(args, data=None):
    cmd = ["gh", "api", *args]
    if data is not None:
        cmd += ["--input", "-"]
    res = subprocess.run(cmd, input=json.dumps(data) if data is not None else None,
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"gh api {' '.join(args)} failed: {res.stderr or res.stdout}")
    return json.loads(res.stdout) if res.stdout.strip() else None


def main():
    repo = sys.argv[1]
    cfg = json.loads((Path(__file__).parent / "arbeitspakete.json").read_text(encoding="utf-8"))

    existing_labels = {l["name"] for l in gh([f"repos/{repo}/labels?per_page=100"])}
    for label in cfg["labels"]:
        if label["name"] not in existing_labels:
            gh([f"repos/{repo}/labels", "-X", "POST"], label)
            print("Label:", label["name"])

    milestones = {m["title"]: m["number"] for m in gh([f"repos/{repo}/milestones?state=all&per_page=100"])}
    for m in cfg["milestones"]:
        if m["title"] not in milestones:
            res = gh([f"repos/{repo}/milestones", "-X", "POST"],
                     {"title": m["title"], "description": m["description"], "due_on": f"{m['due']}T23:59:59Z"})
            milestones[m["title"]] = res["number"]
            print("Meilenstein:", m["title"])

    issues = {}
    page = 1
    while True:
        batch = gh([f"repos/{repo}/issues?state=all&per_page=100&page={page}"])
        if not batch:
            break
        for i in batch:
            issues[i["title"]] = i
        page += 1

    def ensure_issue(title, body, milestone, labels):
        if title in issues:
            return issues[title]
        res = gh([f"repos/{repo}/issues", "-X", "POST"],
                 {"title": title, "body": body, "milestone": milestones[milestone], "labels": labels})
        issues[title] = res
        print("Issue:", title, f"#{res['number']}")
        return res

    for pkg in cfg["packages"]:
        parent = ensure_issue(pkg["title"], pkg["body"], pkg["milestone"], ["arbeitspaket"])
        existing_subs = {s["id"] for s in gh([f"repos/{repo}/issues/{parent['number']}/sub_issues?per_page=100"])}
        for child in pkg["children"]:
            labels = [child["owner"], *child.get("labels", [])]
            sub = ensure_issue(child["title"], child["body"], pkg["milestone"], labels)
            if sub["id"] not in existing_subs:
                gh([f"repos/{repo}/issues/{parent['number']}/sub_issues", "-X", "POST"], {"sub_issue_id": sub["id"]})

    for extra in cfg["extras"]:
        ensure_issue(extra["title"], extra["body"], extra["milestone"], [extra["owner"], *extra.get("labels", [])])


if __name__ == "__main__":
    main()
