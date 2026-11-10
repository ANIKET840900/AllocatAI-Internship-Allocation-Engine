from __future__ import annotations

import csv
import io
from collections.abc import Iterable


def _safe_cell(value: object) -> str:
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def allocation_csv(rows: Iterable[dict]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("candidate_id", "internship_id", "score", "explanation"))
    for row in rows:
        writer.writerow(
            (
                _safe_cell(row.get("candidate_id")),
                _safe_cell(row.get("internship_id")),
                _safe_cell(row.get("score")),
                _safe_cell(row.get("explanation")),
            )
        )
    return output.getvalue().encode("utf-8-sig")


def fairness_csv(report: dict) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("group", "selection_rate"))
    for group, rate in sorted(report.get("selection_rates", {}).items()):
        writer.writerow((_safe_cell(group), _safe_cell(rate)))
    writer.writerow(("demographic_parity_difference", _safe_cell(report.get("demographic_parity_difference"))))
    writer.writerow(("disparate_impact_ratio", _safe_cell(report.get("disparate_impact_ratio"))))
    writer.writerow(("reference_group", _safe_cell(report.get("reference_group"))))
    return output.getvalue().encode("utf-8-sig")


def simple_pdf(lines: Iterable[str]) -> bytes:
    """Create a small one-page text PDF without an optional rendering dependency."""
    escaped = []
    for line in lines:
        ascii_line = str(line).encode("ascii", "replace").decode("ascii")[:110]
        escaped.append(ascii_line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)"))
    commands = ["BT", "/F1 10 Tf", "50 760 Td"]
    for index, line in enumerate(escaped[:48]):
        if index:
            commands.append("0 -14 Td")
        commands.append(f"({line}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    document = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(document))
        document.extend(f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n")
    xref_offset = len(document)
    document.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    document.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    document.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(document)
