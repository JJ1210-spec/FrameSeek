import sys
import threading

from app.services.log_capture import ThreadRoutedStream, capture_thread_output


def test_prints_from_this_thread_go_to_the_sink():
    lines = []
    original = sys.stdout
    with capture_thread_output(lines.append):
        print("[INFO] hello")
        print("multi\nline")
        sys.stdout.write("partial ")
        sys.stdout.write("line\r\n")
    assert lines == ["[INFO] hello", "multi", "line", "partial line"]
    assert sys.stdout is original


def test_unterminated_output_is_flushed_on_exit():
    lines = []
    with capture_thread_output(lines.append):
        sys.stdout.write("no newline at end")
    assert lines == ["no newline at end"]


def test_other_threads_are_not_captured():
    captured = []
    other_thread_ready = threading.Event()
    release = threading.Event()

    def other():
        other_thread_ready.set()
        release.wait(5)
        print("from other thread")

    with capture_thread_output(captured.append):
        t = threading.Thread(target=other)
        t.start()
        other_thread_ready.wait(5)
        print("from worker")
        release.set()
        t.join(5)

    assert captured == ["from worker"]


def test_two_threads_capture_independently():
    results = {}
    barrier = threading.Barrier(2)

    def run(name):
        lines = []
        with capture_thread_output(lines.append):
            barrier.wait(5)
            for i in range(3):
                print(f"{name}-{i}")
            barrier.wait(5)
        results[name] = lines

    threads = [threading.Thread(target=run, args=(n,)) for n in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5)

    assert results == {"a": ["a-0", "a-1", "a-2"], "b": ["b-0", "b-1", "b-2"]}
    assert not isinstance(sys.stdout, ThreadRoutedStream)


def test_captured_output_is_echoed_to_the_original_stream(capsys):
    with capture_thread_output(lambda line: None):
        print("echo me")
    assert "echo me" in capsys.readouterr().out
