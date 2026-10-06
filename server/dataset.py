"""화면 분석 학습 데이터(내 PC 전용): 프레임 이미지·AI 판독·사용자가 고친 값을 폴더에 쌓는다.

- VISION_DATASET_DIR을 지정했을 때만 켜진다(기본 꺼짐). 어디로도 업로드하지 않는다.
- 나중에 파인튜닝을 검토할 때 쓸 정답지 — 사용자 자신의 화면과 수정만 담긴다.
"""
import base64
import json
import pathlib
import re
import shutil
import uuid
from collections.abc import Callable

MAX_FRAMES = 2000  # 이보다 많으면 오래된 프레임부터 지운다
MAX_SKIPPED = 300  # '툴팁 없음'으로 건너뛴 화면(진단용) 상한 — 학습 프레임과 따로 둔다
_ID = re.compile(r"^[0-9]+-[0-9a-f]{8}$")


class DatasetStore:
    def __init__(self, root: str, clock: Callable[[], float]):
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._clock = clock

    def _dir(self, frame_id: str) -> pathlib.Path:
        d = self.root / frame_id
        if not _ID.match(frame_id or "") or not d.is_dir():
            raise KeyError(frame_id)
        return d

    def save_frame(self, image_data_url: str, reading: dict) -> str:
        fid = f"{int(self._clock() * 1000)}-{uuid.uuid4().hex[:8]}"
        d = self.root / fid
        d.mkdir()
        (d / "frame.jpg").write_bytes(base64.b64decode(image_data_url.split(",", 1)[1]))
        (d / "reading.json").write_text(json.dumps(reading, ensure_ascii=False, indent=1), encoding="utf-8")
        frames = sorted(p for p in self.root.iterdir() if p.is_dir() and _ID.match(p.name))
        for old in frames[:-MAX_FRAMES]:
            shutil.rmtree(old, ignore_errors=True)
        return fid

    def save_skipped(self, image_data_url: str, info: dict) -> None:
        """AI에 안 보낸 화면(툴팁 못 찾음)을 진단용으로 남긴다. 마우스를 댔는데 안 읽힌 템을 찾는 데 쓴다."""
        root = self.root / "skipped"
        d = root / f"{int(self._clock() * 1000)}-{uuid.uuid4().hex[:8]}"
        d.mkdir(parents=True)
        (d / "frame.jpg").write_bytes(base64.b64decode(image_data_url.split(",", 1)[1]))
        (d / "info.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
        for old in sorted(root.iterdir())[:-MAX_SKIPPED]:
            shutil.rmtree(old, ignore_errors=True)

    def reading(self, frame_id: str) -> dict:
        return json.loads((self._dir(frame_id) / "reading.json").read_text(encoding="utf-8"))

    def save_correction(self, frame_id: str, signature: str, fields: dict) -> None:
        path = self._dir(frame_id) / "corrections.json"
        rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        rows.append({"signature": signature, "fields": fields, "at": self._clock()})
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    def stats(self) -> dict:
        frames = [p for p in self.root.iterdir() if p.is_dir() and _ID.match(p.name)]
        return {"frames": len(frames), "corrected": sum((p / "corrections.json").exists() for p in frames)}
