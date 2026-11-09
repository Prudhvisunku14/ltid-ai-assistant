import sys
from .service import compare_versions, scan_all
from .sources import make_source
from .store import Store

def main():
    src = make_source(); cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        for d in src.documents(): print(d["name"], [v["id"] for v in d["versions"]])
    elif cmd == "compare":
        r = compare_versions(src, *sys.argv[2:5])
        print("VERIFIED:", r["verified"]["summary"]["text"])
        s = r["interpretation"]["summary"]; print(f"INTERPRETATION [{s['label']}]:", s["text"])
        for c in r["changes"]:
            i = r["interpretation"]["items"][c["id"]]
            print(f"- [{i['severity']}] {c['kind']} @ {c['section']}: {'; '.join(i['reasons'])}")
    elif cmd == "scan":
        print(scan_all(src, Store("history.db")), "comparisons stored in history.db")

if __name__ == "__main__": main()
