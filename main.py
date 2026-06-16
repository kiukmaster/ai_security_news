"""보안·AI 데일리 브리핑 — 진입점.

사용법:
  python main.py            # GUI 실행 (진행 상황을 창으로 표시)
  python main.py --no-gui   # 콘솔 모드 (자동 실행/스케줄러용)
  python main.py --no-gui --open   # 콘솔 모드로 생성 후 보고서 자동 열기
"""

import argparse
import sys
import webbrowser
from pathlib import Path

# Windows 콘솔(cp949 등)에서 이모지·한글 출력이 깨지거나 죽지 않도록 UTF-8 고정
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# src 디렉터리를 import 경로에 추가
SRC = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC))


def run_console(open_after=False, publish_dir=None):
    import pipeline

    def log_cb(msg):
        print(msg, flush=True)

    def progress_cb(cur, total):
        pass  # 콘솔에서는 로그로 충분

    print("=== 보안·AI 데일리 브리핑 (콘솔 모드) ===")
    result = pipeline.run(progress_cb=progress_cb, log_cb=log_cb)
    print(f"\n신규 {result['new_count']}건 / 보고서: {result['report_path']}")

    if publish_dir:
        import publish
        index = publish.publish(result["report_path"], publish_dir)
        print(f"웹 발행 완료 → {index}")
        if open_after:
            webbrowser.open(Path(index).resolve().as_uri())
            return 0
    if open_after:
        webbrowser.open(Path(result["report_path"]).resolve().as_uri())
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="보안·AI 데일리 브리핑 생성기")
    parser.add_argument("--no-gui", action="store_true", help="GUI 없이 콘솔로 실행")
    parser.add_argument("--open", action="store_true", help="생성 후 보고서 자동 열기")
    parser.add_argument("--publish", metavar="DIR", default=None,
                        help="보고서를 웹 발행 폴더(예: docs)로 출력 (GitHub Pages용)")
    args = parser.parse_args(argv)

    if args.no_gui or args.publish:
        return run_console(open_after=args.open, publish_dir=args.publish)

    try:
        import gui
        gui.main()
        return 0
    except Exception as e:  # GUI 사용 불가 환경 → 콘솔로 폴백
        print(f"GUI 실행 불가({e}) — 콘솔 모드로 전환합니다.", file=sys.stderr)
        return run_console(open_after=args.open)


if __name__ == "__main__":
    raise SystemExit(main())
