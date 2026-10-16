import ast
import os
import sys
import json
import subprocess
from typing import Set, List, Dict

class DependencyManager:
    """
    Intelligent dependency inspector and database manager:
    1. Uses Python AST to extract all imports from generated code.
    2. Filters out Python standard library and local module imports.
    3. Resolves import names to exact PyPI packages via dependency_database.json.
    4. Auto-saves newly discovered packages into the persistent database.
    5. Ensures packages are installed locally and writes complete requirements.txt for cloud deployment.
    """

    DB_PATH = os.path.join(os.path.dirname(__file__), "dependency_database.json")

    @classmethod
    def load_database(cls) -> Dict[str, str]:
        if os.path.exists(cls.DB_PATH):
            try:
                with open(cls.DB_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    @classmethod
    def save_database(cls, db: Dict[str, str]):
        try:
            with open(cls.DB_PATH, "w", encoding="utf-8") as f:
                json.dump(db, f, indent=2)
        except Exception:
            pass

    @classmethod
    def extract_imported_modules(cls, code: str) -> Set[str]:
        """Parses Python code using AST and extracts all top-level imported module names."""
        modules = set()
        if not code:
            return modules

        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        modules.add(top)
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.level == 0:
                        top = node.module.split(".")[0]
                        modules.add(top)
        except SyntaxError:
            # Fallback regex if code has syntax oddities
            import re
            matches = re.findall(r"^\s*(?:import|from)\s+([a-zA-Z0-9_]+)", code, re.MULTILINE)
            for m in matches:
                modules.add(m)

        return modules

    @classmethod
    def filter_third_party(cls, modules: Set[str]) -> Set[str]:
        """Filters out Python standard library modules and internal project files."""
        # Builtins and stdlib module names
        stdlib = getattr(sys, "stdlib_module_names", set())
        internal_modules = {"app", "test_app", "core", "agents", "builtins", "__future__"}

        third_party = set()
        for mod in modules:
            mod_clean = mod.strip()
            if not mod_clean:
                continue
            if mod_clean in internal_modules or mod_clean.startswith("_"):
                continue
            if mod_clean in stdlib:
                continue
            third_party.add(mod_clean)

        return third_party

    @classmethod
    def resolve_requirements(cls, code: str) -> List[str]:
        """
        Analyzes code, detects third-party imports, checks against dependency database,
        and returns a sorted list of requirement strings (e.g. ['plotly>=5.18.0', 'pandas>=2.0.0']).
        """
        imported = cls.extract_imported_modules(code)
        third_party = cls.filter_third_party(imported)
        db = cls.load_database()

        updated_db = False
        resolved_reqs = {"pytest>=8.0.0"}

        # Always include streamlit if app uses UI
        if "streamlit" in imported or "st." in code:
            resolved_reqs.add("streamlit>=1.35.0")

        for mod in third_party:
            if mod in db:
                resolved_reqs.add(db[mod])
            else:
                # Discovered new third-party dependency!
                req_str = f"{mod}>=1.0.0"
                db[mod] = req_str
                resolved_reqs.add(req_str)
                updated_db = True
                print(f"[DependencyManager] Discovered & registered new third-party module: '{mod}'")

        if updated_db:
            cls.save_database(db)

        return sorted(list(resolved_reqs))

    @classmethod
    def ensure_module_installed(cls, module_name: str) -> bool:
        """Checks if a module can be imported; if not, attempts automatic pip install."""
        stdlib = getattr(sys, "stdlib_module_names", set())
        if module_name in stdlib or module_name in {"app", "test_app"}:
            return True

        try:
            __import__(module_name)
            return True
        except ImportError:
            pass

        # Resolve pip package name
        db = cls.load_database()
        req_entry = db.get(module_name, module_name)
        pkg_name = req_entry.split(">=")[0].split("==")[0].strip()

        print(f"[DependencyManager] Auto-installing required package '{pkg_name}' into environment...")
        try:
            res = subprocess.run([sys.executable, "-m", "pip", "install", pkg_name], capture_output=True, timeout=60)
            return res.returncode == 0
        except Exception as e:
            print(f"[DependencyManager] Installation failed: {e}")
            return False
