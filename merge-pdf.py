#!/usr/bin/env python3
"""여러 PDF를 하나로 합치는 간단한 CLI.

입력으로 파일, 폴더, 와일드카드(*.pdf)를 모두 줄 수 있습니다.
(Windows cmd/PowerShell은 와일드카드를 확장해 주지 않으므로 스크립트가 직접 처리합니다.)

사용법:
    python merge-pdf.py -o merged.pdf a.pdf b.pdf c.pdf
    python merge-pdf.py -o merged.pdf ./work              # 폴더 안의 모든 PDF
    python merge-pdf.py -o merged.pdf ./work/*.pdf        # 와일드카드
    python merge-pdf.py -o merged.pdf ./work -r           # 하위 폴더까지
    python merge-pdf.py -o merged.pdf a.pdf enc.pdf -p "enc.pdf=비밀번호"

폴더/와일드카드로 찾은 파일은 이름 순(자연 정렬: 2.pdf < 10.pdf)으로 합칩니다.
여러 입력을 섞으면 입력한 순서를 유지합니다.

필요 패키지: pypdf  (pip install pypdf)
"""
import argparse
import glob
import re
import sys
from pathlib import Path

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    sys.exit("pypdf가 필요합니다: pip install pypdf")

GLOB_CHARS = set("*?[")


def natural_key(path):
    """2.pdf < 10.pdf 가 되도록 숫자 부분을 숫자로 비교."""
    s = str(path).lower()
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def expand_inputs(items, recursive=False, exclude=None):
    """파일/폴더/와일드카드를 실제 PDF 파일 목록으로 확장."""
    result = []
    for item in items:
        p = Path(item)
        if p.is_dir():
            it = p.rglob("*") if recursive else p.iterdir()
            found = [f for f in it if f.is_file() and f.suffix.lower() == ".pdf"]
            if not found:
                sys.exit(f"폴더에 PDF가 없습니다: {p}")
        elif GLOB_CHARS & set(item):
            found = [Path(m) for m in glob.glob(item, recursive=recursive)
                     if Path(m).is_file()]
            if not found:
                sys.exit(f"패턴과 일치하는 파일이 없습니다: {item}")
        else:
            if not p.is_file():
                sys.exit(f"파일을 찾을 수 없습니다: {p}")
            result.append(p)
            continue
        result.extend(sorted(found, key=natural_key))

    # 출력 파일이 폴더/패턴에 걸려 입력으로 들어가는 것을 방지
    if exclude is not None:
        result = [f for f in result if f.resolve() != exclude]
    if not result:
        sys.exit("합칠 PDF 파일이 없습니다.")
    return result


def parse_passwords(items):
    """'파일명=비밀번호' 목록을 {파일명: 비밀번호} 딕셔너리로 변환."""
    result = {}
    for item in items or []:
        name, sep, pw = item.partition("=")
        if not sep:
            sys.exit(f"--password 형식 오류 (파일명=비밀번호): {item}")
        result[Path(name).name] = pw
    return result


def merge(inputs, output, bookmarks=True, passwords=None):
    passwords = passwords or {}
    writer = PdfWriter()
    total_pages = 0

    for p in inputs:
        try:
            reader = PdfReader(str(p))
            if reader.is_encrypted:
                pw = passwords.get(p.name)
                if pw is None or not reader.decrypt(pw):
                    sys.exit(f"암호화된 파일입니다. -p '{p.name}=비밀번호'를 지정하세요: {p}")
            writer.append(reader, outline_item=p.stem if bookmarks else None)
        except SystemExit:
            raise
        except Exception as e:
            sys.exit(f"읽기 실패: {p} ({e})")
        total_pages += len(reader.pages)
        print(f"+ {p} ({len(reader.pages)}p)")

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        writer.write(f)
    writer.close()
    print(f"완료: {out} (총 {total_pages}p, 파일 {len(inputs)}개)")


def main():
    ap = argparse.ArgumentParser(description="여러 PDF를 하나로 합칩니다.")
    ap.add_argument("inputs", nargs="+",
                    help="PDF 파일, 폴더, 또는 와일드카드 (예: ./work/*.pdf)")
    ap.add_argument("-o", "--output", required=True, help="출력 PDF 경로")
    ap.add_argument("-r", "--recursive", action="store_true",
                    help="폴더 입력 시 하위 폴더까지 포함 (패턴에서는 ** 사용 가능)")
    ap.add_argument("--no-bookmarks", action="store_true", help="파일별 북마크 생성 안 함")
    ap.add_argument("-p", "--password", action="append", metavar="파일명=비밀번호",
                    help="암호화된 입력 파일용 (여러 번 지정 가능)")
    args = ap.parse_args()

    out = Path(args.output).resolve()
    files = expand_inputs(args.inputs, recursive=args.recursive, exclude=out)
    if any(f.resolve() == out for f in files):
        sys.exit("출력 파일이 입력 파일과 같습니다.")

    merge(files, args.output,
          bookmarks=not args.no_bookmarks,
          passwords=parse_passwords(args.password))


if __name__ == "__main__":
    main()