#!/usr/bin/env python3


'''
The methods are taken from
https://github.com/yxdragon/sknw
'''

import networkx as nx
import numpy as np
from numba import jit


# get neighbors d index
def neighbors(shape):
    dim = len(shape)
    block = np.ones([3] * dim)
    block[tuple([1] * dim)] = 0
    idx = np.where(block > 0)
    idx = np.array(idx, dtype=np.uint8).T
    idx = np.array(idx - [1] * dim)
    acc = np.cumprod((1,) + shape[::-1][:-1])
    return np.dot(idx, acc[::-1])


@jit(nopython=True)  # my mark
def mark(img, nbs):  # mark the array use (0, 1, 2)
    img = img.ravel()
    for p in range(len(img)):
        if img[p] == 0:
            continue
        s = 0
        for dp in nbs:
            if img[p + dp] != 0:
                s += 1
        if s == 2:
            img[p] = 1
        else:
            img[p] = 2


@jit(nopython=True)  # trans index to r, c...
def idx2rc(idx, acc):
    rst = np.zeros((len(idx), len(acc)), dtype=np.int16)
    for i in range(len(idx)):
        for j in range(len(acc)):
            rst[i, j] = idx[i] // acc[j]
            idx[i] -= rst[i, j] * acc[j]
    rst -= 1
    return rst


@jit(nopython=True)  # fill a node (may be two or more points)
def fill(img, p, num, nbs, acc, buf):
    back = img[p]
    img[p] = num
    buf[0] = p
    cur = 0
    s = 1

    while True:
        p = buf[cur]
        for dp in nbs:
            cp = p + dp
            if img[cp] == back:
                img[cp] = num
                buf[s] = cp
                s += 1
        cur += 1
        if cur == s:
            break
    return idx2rc(buf[:s], acc)


# trace the edge and use a buffer, then buf.copy, if use [] numba not works
@jit(nopython=True)
def trace(img, p, nbs, acc, buf):
    c1 = 0
    c2 = 0
    newp = 0
    cur = 1
    while True:
        buf[cur] = p
        img[p] = 0
        cur += 1
        for dp in nbs:
            cp = p + dp
            if img[cp] >= 10:
                if c1 == 0:
                    c1 = img[cp]
                    buf[0] = cp
                else:
                    c2 = img[cp]
                    buf[cur] = cp
            if img[cp] == 1:
                newp = cp
        p = newp
        if c2 != 0:
            break
    return (c1 - 10, c2 - 10, idx2rc(buf[:cur + 1], acc))


@jit(nopython=True)  # parse the image then get the nodes and edges
def parse_struc(img, pts, nbs, acc):
    img = img.ravel()
    buf = np.zeros(131072, dtype=np.int64)
    num = 10
    nodes = []
    for p in pts:
        if img[p] == 2:
            nds = fill(img, p, num, nbs, acc, buf)
            num += 1
            nodes.append(nds)
    edges = []
    for p in pts:
        for dp in nbs:
            if img[p + dp] == 1:
                edge = trace(img, p + dp, nbs, acc, buf)
                edges.append(edge)
    return nodes, edges

# use nodes and edges build a networkx graph


def build_graph(nodes, edges, multi=False):
    graph = nx.MultiGraph() if multi else nx.Graph()
    for i in range(len(nodes)):
        graph.add_node(i, pts=nodes[i], o=nodes[i].mean(axis=0))
    for s, e, pts in edges:
        ln = np.linalg.norm(pts[1:] - pts[:-1], axis=1).sum()
        graph.add_edge(s, e, pts=pts, weight=ln)
    return graph


def buffer(ske):
    buf = np.zeros(tuple(np.array(ske.shape) + 2), dtype=np.uint16)
    buf[tuple([slice(1, -1)] * buf.ndim)] = ske
    return buf


def mark_node(ske):
    buf = buffer(ske)
    nbs = neighbors(buf.shape)
    acc = np.cumprod((1,)+buf.shape[::-1][:-1])[::-1]
    mark(buf, nbs)
    return buf


def build_sknw(ske, multi=False):
    buf = buffer(ske)
    nbs = neighbors(buf.shape)
    acc = np.cumprod((1,)+buf.shape[::-1][:-1])[::-1]
    mark(buf, nbs)
    pts = np.array(np.where(buf.ravel() == 2))[0]
    nodes, edges = parse_struc(buf, pts, nbs, acc)
    return build_graph(nodes, edges, multi)

# draw the graph


def draw_graph(img, graph, cn=255, ce=128):
    acc = np.cumprod((1,) + img.shape[::-1][:-1])[::-1]
    img = img.ravel()
    for (s, e) in graph.edges():
        eds = graph[s][e]
        if isinstance(graph, nx.MultiGraph):
            for i in eds:
                pts = eds[i]['pts']
                img[np.dot(pts, acc)] = ce
        else:
            img[np.dot(eds['pts'], acc)] = ce
    for idx in graph.nodes():
        pts = graph.nodes[idx]['pts']
        img[np.dot(pts, acc)] = cn


if __name__ == '__main__':
    import matplotlib.pyplot as plt

    img = np.array([
        [0, 0, 0, 1, 0, 0, 0, 0, 0],
        [0, 0, 0, 1, 0, 0, 0, 0, 0],
        [0, 0, 0, 1, 0, 0, 0, 0, 0],
        [1, 1, 1, 1, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 1, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 1, 0, 0, 0],
        [0, 0, 0, 0, 0, 1, 1, 1, 1],
        [0, 0, 0, 0, 1, 0, 0, 0, 0],
        [0, 0, 0, 1, 0, 0, 0, 0, 0]])

    node_img = mark_node(img)
    graph = build_sknw(img)

    plt.imshow(node_img[1:-1, 1:-1], cmap='gray')

    # draw edges by pts
    for (s, e) in graph.edges():
        ps = graph[s][e]['pts']
        plt.plot(ps[:, 1], ps[:, 0], 'green')

    # draw node by o
    nodes = graph.nodes()
    ps = np.array([nodes[i]['o'] for i in nodes])
    plt.plot(ps[:, 1], ps[:, 0], 'r.')

    # title and show
    plt.title('Build Graph')
    plt.show()
