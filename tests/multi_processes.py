import multiprocessing as mp


def gn(x):
    breakpoint()
    return x + 1


def fn(x):
    breakpoint()
    p3 = mp.Process(target=gn, args=[5])
    p3.start()
    p3.join()
    return x + 2


if __name__ == "__main__":
    p = mp.Process(target=fn, args=[3])
    p2 = mp.Process(target=fn, args=[4])
    p.start()
    p2.start()
    p.join()
    p2.join()
