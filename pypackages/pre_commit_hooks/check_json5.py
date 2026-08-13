# Source: <https://github.com/pre-commit/pre-commit-hooks/blob/39ab2ed/pre_commit_hooks/check_json.py>  # noqa: E501
import argparse
import concurrent.futures
import multiprocessing
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence
from typing import Tuple

import json5


DEFAULT_BATCH_SIZE = 8


def raise_duplicate_keys(
        ordered_pairs: List[Tuple[str, Any]],
) -> Dict[str, Any]:
    d = {}
    for key, val in ordered_pairs:
        if key in d:
            raise ValueError(f'Duplicate key: {key}')
        else:
            d[key] = val
    return d


def check_file(filename: str) -> Optional[str]:
    """Return an error message when a JSON5 file cannot be decoded."""
    with open(filename, 'rb') as f:
        try:
            json5.load(f, object_pairs_hook=raise_duplicate_keys)
        except ValueError as exc:
            return f'{filename}: Failed to json decode ({exc})'
    return None


def check_batch(filenames: Sequence[str]) -> List[Optional[str]]:
    """Check a batch of files, preserving its input order."""
    return [check_file(filename) for filename in filenames]


def batches(filenames: Sequence[str], batch_size: int) -> List[Sequence[str]]:
    """Split filenames into bounded batches for worker processes."""
    return [
        filenames[start:start + batch_size]
        for start in range(0, len(filenames), batch_size)
    ]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    cpu_count = multiprocessing.cpu_count()
    parser.add_argument(
        '--jobs',
        type=int,
        default=cpu_count,
        help=f'Number of worker processes to use (default: available CPUs - {cpu_count}).',
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f'Files assigned to each worker task (default: {DEFAULT_BATCH_SIZE}).',
    )
    parser.add_argument('filenames', nargs='*', help='Filenames to check.')
    args = parser.parse_args(argv)

    if args.jobs == 0:
        args.jobs = cpu_count
    if args.jobs < 1:
        parser.error('--jobs must be at least 0')
    if args.batch_size < 0:
        parser.error('--batch-size must be at least 0')

    retval = 0
    if len(args.filenames) < args.batch_size or args.jobs == 1 or args.batch_size == 0:
        batch_results = (check_batch(args.filenames),)
    else:
        file_batches = batches(args.filenames, args.batch_size)
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.jobs) as executor:
            batch_results = tuple(executor.map(check_batch, file_batches))

    for errors in batch_results:
        for error in errors:
            if error is not None:
                print(error)
                retval = 1
    return retval


if __name__ == '__main__':
    raise SystemExit(main())
