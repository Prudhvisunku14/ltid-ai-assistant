"""SQLite history of comparisons (app-owned DB; never touches the source documents)."""
import json, sqlite3, time

class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("""CREATE TABLE IF NOT EXISTS comparisons(
            id INTEGER PRIMARY KEY, doc TEXT, v_old TEXT, v_new TEXT, created REAL,
            n_changes INT, n_impacting INT, max_severity TEXT, result TEXT, UNIQUE(doc,v_old,v_new))""")
    def save(self, doc, a, b, result):
        s = result["interpretation"]["summary"]
        self.db.execute("INSERT OR REPLACE INTO comparisons(doc,v_old,v_new,created,n_changes,n_impacting,max_severity,result) VALUES(?,?,?,?,?,?,?,?)",
                        (doc, a, b, time.time(), len(result["changes"]), s["impacting"], s["max_severity"], json.dumps(result)))
        self.db.commit()
    def history(self):
        r = self.db.execute("SELECT id,doc,v_old,v_new,created,n_changes,n_impacting,max_severity FROM comparisons ORDER BY doc, id").fetchall()
        k = ["id", "doc", "v_old", "v_new", "created", "n_changes", "n_impacting", "max_severity"]
        return [dict(zip(k, x)) for x in r]
    def get(self, cid):
        r = self.db.execute("SELECT result FROM comparisons WHERE id=?", (cid,)).fetchone()
        return json.loads(r[0]) if r else None
