"""Fixture rapat minimal untuk pengujian (tanpa audio & tanpa model)."""

import time

SEGMENTS = [
    {"start": 0.0, "end": 4.2, "speaker": "S1", "text": "Kita perlu absen antar kantor."},
    {"start": 4.2, "end": 9.8, "speaker": "S2", "text": "Iya, limit pinjaman 20% dari gaji pokok."},
    {"start": 9.8, "end": 14.0, "speaker": "S1", "text": "Saya kirim draft ERD minggu ini."},
]

EVIDENCE = [{"t": "00:00:04", "quote": "limit pinjaman 20% dari gaji pokok"}]

FACTS = {
    "meeting": {
        "title": "Rapat Uji CI",
        "date": "2026-01-15",
        "duration_min": 12.5,
        "topics": ["Absensi", "Pinjaman"],
    },
    "summary": {
        "tldr": ["Absen antar kantor disetujui.", "Limit pinjaman 20% gaji pokok."],
        "narrative": "Rapat membahas absensi lintas kantor dan batas pinjaman karyawan.",
    },
    "decisions": [
        {"id": "D-01", "text": "Absen dapat dilakukan di kantor mana pun.",
         "confidence": "high", "evidence": EVIDENCE},
    ],
    "requirements": [
        {"id": "R-01", "type": "business_rule", "text": "Limit pinjaman 20% dari gaji pokok.",
         "priority": "must", "confidence": "high", "evidence": EVIDENCE},
    ],
    "action_items": [
        {"id": "A-01", "task": "Kirim draft ERD", "owner": "Indra",
         "owner_confidence": "explicit", "due": "2026-01-20", "status": "open",
         "evidence": [{"t": "00:00:09", "quote": "Saya kirim draft ERD minggu ini"}]},
    ],
    "open_questions": [
        {"id": "Q-01", "question": "Berapa masa kerja minimum?", "status": "needs_confirmation",
         "evidence": []},
    ],
    "glossary_candidates": [{"term": "Rempoa", "as_spoken": "rempoha"}],
}

ARTIFACTS = {
    "brd": {
        "title": "BRD Rapat Uji CI",
        "background": "Perlu penyesuaian aturan absensi dan pinjaman.",
        "objectives": ["Otomatiskan absensi lintas kantor"],
        "success_metrics": ["100% absensi lintas kantor tercatat"],
        "in_scope": ["Absensi lintas kantor"],
        "out_of_scope": ["Payroll"],
        "stakeholders": [{"role": "HR", "interest": "kepatuhan"}],
        "business_requirements": [
            {"id": "BR-01", "text": "Absensi lintas kantor", "priority": "must", "refs": ["R-01"]},
        ],
        "assumptions": ["Data karyawan tersedia"],
        "risks": [{"risk": "Data tidak lengkap", "impact": "sedang", "mitigation": "validasi"}],
        "dependencies": ["Modul HR"],
        "open_questions": ["Q-01"],
    },
    "epics": [
        {
            "id": "EP-01",
            "title": "Absensi Lintas Kantor",
            "goal": "Karyawan dapat absen di kantor mana pun.",
            "value": "Mengurangi pengajuan manual.",
            "in_scope": ["absensi"],
            "out_of_scope": ["payroll"],
            "success_metric": "0 pengajuan manual",
            "refs": ["R-01"],
            "stories": [
                {
                    "id": "US-01",
                    "as_a": "karyawan",
                    "i_want": "absen di kantor mana pun",
                    "so_that": "kehadiran tetap tercatat",
                    "acceptance": [
                        {"given": "karyawan di kantor lain", "when": "absen", "then": "tercatat"},
                    ],
                    "priority": "must",
                    "refs": ["R-01"],
                },
            ],
        },
    ],
}


def transcript() -> dict:
    return {
        "file": "rapat_uji.mp3",
        "engine": "faster-whisper/turbo/auto",
        "audio_s": 14.0,
        "segments": len(SEGMENTS),
        "segments_data": SEGMENTS,
        "speakers": {"S1": 8.2, "S2": 5.6},
        "unclear": 0,
    }


def meta(meeting_id: str = "ci_meeting") -> dict:
    return {
        "id": meeting_id,
        "title": FACTS["meeting"]["title"],
        "date": FACTS["meeting"]["date"],
        "duration_min": FACTS["meeting"]["duration_min"],
        "topics": FACTS["meeting"]["topics"],
        "audio": "",
        "docs": {},
        "created_at": time.time(),
        "archived": False,
    }
