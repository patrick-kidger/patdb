import multiprocessing as mp


def fn(x):
    # Not testing subprocesses as `mp.Pool` creates daemon processes, which cannot have
    # children.
    breakpoint()
    return x + 2


if __name__ == "__main__":
    with mp.Pool() as pool:
        pool.map(fn, [3, 4])
