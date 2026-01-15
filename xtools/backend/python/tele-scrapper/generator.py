import os
import codecs
import re
import shutil
import sqlite3
import json

# Global Regex Patterns
EMAIL_VALIDATION = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
METADATA_PATTERN = re.compile(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}):([^|\s]+)\s*\|')
DIRECT_EMAIL_PATTERN = re.compile(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}):([^\s\n\r]+)')
URL_EMAIL_PIPE_PATTERN = re.compile(r'(https?://[^|\s]+):([^\s:]+):([^|\s]+)\s*\|')
URL_EMAIL_PATTERN = re.compile(r'(https?://[^:\s]+?):([^\s:]+):([^\s]+)')
LOG_PATTERN = re.compile(r'[^:]*:\s*([^\s:]+)\s*:\s*([^\s]+)')

class WordlistGenerator:
    def __init__(self, log_callback):
        self.log = log_callback
        self.combolists_dir = "combolists"
        self.wordlists_dir = "wordlists"
        self.progress_file = "progress.json"
        self.chunk_size = 50000 
        self.progress_data = self._load_progress()

    def _load_progress(self):
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r') as f:
                    return json.load(f)
            except: return {}
        return {}

    def _save_progress(self):
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress_data, f, indent=4)

    def generate(self):
        """Original name preserved. Single-threaded with 4-digit number filtering."""
        self.log(f"🔄 Resuming session via progress.json...")
        
        if not os.path.exists(self.wordlists_dir):
            os.makedirs(self.wordlists_dir)

        db_configs = {
            "u": os.path.join(self.wordlists_dir, "emails.db"),
            "p": os.path.join(self.wordlists_dir, "passwords.db"),
            "c": os.path.join(self.wordlists_dir, "combos.db")
        }

        conns = {k: sqlite3.connect(path) for k, path in db_configs.items()}
        cursors = {k: conn.cursor() for k, conn in conns.items()}

        for conn in conns.values():
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = OFF")
            conn.execute("CREATE TABLE IF NOT EXISTS data (val TEXT PRIMARY KEY)")
            conn.commit()

        all_files = []
        for root, _, files in os.walk(self.combolists_dir):
            for f in files:
                all_files.append(os.path.join(root, f))

        patterns = [METADATA_PATTERN, DIRECT_EMAIL_PATTERN, URL_EMAIL_PIPE_PATTERN, URL_EMAIL_PATTERN, LOG_PATTERN]

        for file_path in all_files:
            status = self.progress_data.get(file_path, {"line": 0, "complete": False})
            if status["complete"]: continue

            self.log(f"📂 Processing: {os.path.basename(file_path)} (Line {status['line']})")
            
            current_line_count = 0
            u_batch, p_batch, c_batch = [], [], []

            try:
                with codecs.open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        current_line_count += 1
                        if current_line_count <= status["line"]: continue

                        line = line.strip()
                        if not line: continue

                        user, pwd = None, None
                        for pattern in patterns:
                            match = pattern.search(line)
                            if match:
                                groups = match.groups()
                                if len(groups) == 2:
                                    user, pwd = groups[0], groups[1]
                                elif len(groups) == 3:
                                    user, pwd = groups[1], groups[2]
                                break

                        if not user and ':' in line:
                            parts = line.split(':')
                            if len(parts) >= 2:
                                user, pwd = parts[0], ":".join(parts[1:])

                        if user and pwd:
                            clean_user = user.strip()
                            clean_pwd = pwd.strip()
                            
                            # --- NEW FILTER LOGIC ---
                            # Discard if the email starts with 4 digits
                            if len(clean_user) >= 4 and clean_user[:4].isdigit():
                                continue
                            # ------------------------

                            u_batch.append((clean_user,))
                            p_batch.append((clean_pwd,))
                            if EMAIL_VALIDATION.search(clean_user):
                                c_batch.append((f"{clean_user}:{clean_pwd}",))

                        if current_line_count % self.chunk_size == 0:
                            self._commit_batches(cursors, conns, u_batch, p_batch, c_batch)
                            u_batch, p_batch, c_batch = [], [], []
                            self.progress_data[file_path] = {"line": current_line_count, "complete": False}
                            self._save_progress()

                self._commit_batches(cursors, conns, u_batch, p_batch, c_batch)
                self.progress_data[file_path] = {"line": current_line_count, "complete": True}
                self._save_progress()
                self.log(f"✅ Completed file: {os.path.basename(file_path)}")

            except Exception as e:
                self.log(f"❌ Error in {file_path}: {e}")
                continue

        for conn in conns.values():
            conn.close()
        self.log("🏁 All files processed and indexed.")

    def _commit_batches(self, cursors, conns, u, p, c):
        if u: cursors["u"].executemany("INSERT OR IGNORE INTO data VALUES (?)", u)
        if p: cursors["p"].executemany("INSERT OR IGNORE INTO data VALUES (?)", p)
        if c: cursors["c"].executemany("INSERT OR IGNORE INTO data VALUES (?)", c)
        for conn in conns.values():
            conn.commit()

    def _write_set_to_file(self, cursor, file_path): pass
    def _rename_old_files(self): pass
    def _log_old_summary(self): pass

def run_generator(log_callback):
    generator = WordlistGenerator(log_callback)
    generator.generate()
