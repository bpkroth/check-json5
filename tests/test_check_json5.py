import pytest
from pre_commit_hooks import check_json5
from pre_commit_hooks.check_json5 import main


def fail_if_called(*args, **kwargs):
    raise AssertionError('worker process should not be created')


@pytest.mark.parametrize(
    ('filename', 'expected_retval'),
    [
        # Valid JSON (subset of JSON5)
        ('ok_json.json', 0),
        # JSON5-specific features
        ('ok_json5_with_comments.json5', 0),
        ('ok_json5_with_trailing_comma.json5', 0),
        ('ok_json5_unquoted_keys.json5', 0),
        ('ok_json5_numbers.json5', 0),
        ('ok_json5_multiline_string.json5', 0),
        # Invalid files
        ('bad_json5_syntax.json5', 1),
        ('duplicate_key.json5', 1),
        ('nested_duplicate_key.json5', 1),
    ],
)
def test_main(capsys, resource_path, filename, expected_retval):
    ret = main([resource_path(filename)])
    assert ret == expected_retval
    if expected_retval == 1:
        stdout, _ = capsys.readouterr()
        assert filename in stdout


def test_duplicate_key_error_message(capsys, resource_path):
    """Test that duplicate key errors include the key name."""
    ret = main([resource_path('duplicate_key.json5')])
    assert ret == 1
    stdout, _ = capsys.readouterr()
    assert 'Duplicate key' in stdout
    assert 'hello' in stdout


def test_non_utf8_file(tmp_path):
    """Test that non-UTF8 files are rejected."""
    f = tmp_path / 't.json5'
    f.write_bytes(b'\xa9\xfe\x12')
    assert main([str(f)]) == 1


def test_multiple_files(resource_path):
    """Test processing multiple files at once."""
    files = [
        resource_path('ok_json.json'),
        resource_path('ok_json5_with_comments.json5'),
    ]
    assert main(['--jobs=2', '--batch-size=1', *files]) == 0


def test_files_smaller_than_batch_do_not_create_workers(
        monkeypatch,
        resource_path,
) -> None:
    monkeypatch.setattr(
        check_json5.concurrent.futures,
        'ProcessPoolExecutor',
        fail_if_called,
    )
    assert check_json5.main([
        '--batch-size=2', resource_path('ok_json.json'),
    ]) == 0


def test_single_job_with_large_batch_does_not_create_workers(
        monkeypatch,
        resource_path,
) -> None:
    monkeypatch.setattr(
        check_json5.concurrent.futures,
        'ProcessPoolExecutor',
        fail_if_called,
    )
    files = [
        resource_path('ok_json.json'),
        resource_path('ok_json5_numbers.json5'),
        resource_path('ok_json5_with_comments.json5'),
    ]
    assert check_json5.main([
        '--jobs=1', '--batch-size=2', *files,
    ]) == 0


def test_zero_batch_size_does_not_create_workers(
        monkeypatch,
        resource_path,
) -> None:
    monkeypatch.setattr(
        check_json5.concurrent.futures,
        'ProcessPoolExecutor',
        fail_if_called,
    )
    files = [
        resource_path('ok_json.json'),
        resource_path('ok_json5_numbers.json5'),
    ]
    assert check_json5.main(['--batch-size=0', *files]) == 0


def test_zero_jobs_uses_cpu_count(monkeypatch, resource_path) -> None:
    seen = []

    class Executor:
        def __init__(self, max_workers):
            seen.append(max_workers)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def map(self, function, file_batches):
            return map(function, file_batches)

    monkeypatch.setattr(check_json5.multiprocessing, 'cpu_count', lambda: 3)
    monkeypatch.setattr(
        check_json5.concurrent.futures,
        'ProcessPoolExecutor',
        Executor,
    )
    files = [
        resource_path('ok_json.json'),
        resource_path('ok_json5_numbers.json5'),
    ]
    assert check_json5.main(['--jobs=0', '--batch-size=1', *files]) == 0
    assert seen == [3]


def test_multiple_files_with_one_bad(capsys, resource_path):
    """Test that one bad file causes overall failure."""
    files = [
        resource_path('ok_json.json'),
        resource_path('bad_json5_syntax.json5'),
        resource_path('ok_json5_with_comments.json5'),
    ]
    ret = main(['--jobs=2', '--batch-size=1', *files])
    assert ret == 1
    stdout, _ = capsys.readouterr()
    assert 'bad_json5_syntax.json5' in stdout
    # Good files should not appear in error output
    assert 'ok_json.json' not in stdout


def test_empty_file(tmp_path):
    """Test that empty files are rejected (not valid JSON5)."""
    f = tmp_path / 'empty.json5'
    f.write_text('')
    assert main([str(f)]) == 1


def test_no_files():
    """Test with no files provided."""
    assert main([]) == 0


@pytest.mark.parametrize('option', ('--jobs=-1', '--batch-size=-1'))
def test_parallel_options_must_not_be_negative(option):
    with pytest.raises(SystemExit):
        main([option])
