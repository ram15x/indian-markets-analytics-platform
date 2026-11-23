import sys, shutil; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import pytest
from imap import manifest as M

DATA = Path(__file__).parent.parent / "data"


def test_repo_data_matches_manifest():
    M.verify(DATA)


def test_tampered_file_refused(tmp_path):
    for f in M.FILES + (M.NAME,):
        if (DATA / f).exists():
            (tmp_path / f).parent.mkdir(parents=True, exist_ok=True); shutil.copy(DATA / f, tmp_path / f)
    M.verify(tmp_path)
    p = tmp_path / "renames.csv"; p.write_text(p.read_text() + "x,1,y,,z,UNVERIFIED\n")
    with pytest.raises(M.ManifestError, match="renames.csv"):
        M.verify(tmp_path)


def test_missing_manifest_refused(tmp_path):
    with pytest.raises(M.ManifestError, match="missing"):
        M.verify(tmp_path)
