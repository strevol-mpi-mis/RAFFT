"""Take the output of rafft and produce a latex file to display the fold paths.

It uses varna to produce 2ndary structures.
"""

import argparse
import subprocess
from os.path import realpath, dirname
from utils import paired_positions
from numpy import array, zeros, exp, matmul
import matplotlib.pyplot as plt


def parse_rafft_output(infile):
    results = []
    with open(infile) as rafft_out:
        seq = rafft_out.readline().strip()
        for l in rafft_out:
            if l.startswith("# --"):
                results += [[]]
            else:
                struct, nrj = l.strip().split()
                results[-1] += [(struct, float(nrj))]
    return results, seq


def get_connected_prev(cur_struct, prev_pos):
    "get the connected structures"
    cur_pairs = set(paired_positions(cur_struct))
    res = []
    for si, (struct, nrj) in enumerate(prev_pos):
        pairs = set(paired_positions(struct))
        if len(pairs - cur_pairs) == 0:
            res += [si]
    return res


def parse_arguments():
    """Parsing command line
    """
    parser = argparse.ArgumentParser(description="Uses VARNA to plot the fast-paths predicted by RAFFT. !! It creates a temporary directory in the current folder!!")
    parser.add_argument('rafft_out', help="rafft_output")
    parser.add_argument('--out', '-o', help="output file")
    parser.add_argument('--width', '-wi', help="figure width", type=int, default=500)
    parser.add_argument('--height', '-he', help="figure height", type=int, default=300)
    parser.add_argument('--res_varna', '-rv', help="change varna resolution", type=float, default=1.0)
    parser.add_argument('--line_thick', '-lt', help="line thickness", type=int, default=2)
    parser.add_argument('--font_size', '-fs', help="font size for the colors", type=int, default=3)
    parser.add_argument('--varna_jar', help="varna jar (please download it from VARNA website)")
    parser.add_argument('--no_col', action="store_true", help="don't use the color gradient for the edges")
    parser.add_argument('--no_fig', action="store_true", help="you already computed the structures previously?")
    return parser.parse_args()


def main():
    args = parse_arguments()

    fast_paths, seq = parse_rafft_output(args.rafft_out)

    # to draw the paths
    nb_steps = len(fast_paths)
    nb_saved = len(fast_paths[-1])

    # transition matrix
    struct_list = [st for el in fast_paths for st, _ in el]
    struct_map = {st: si for si, st in enumerate(struct_list)}
    map2_struct = {}
    map2_struct[0] = (0, 0)
    nb_struct = len(struct_list)
    transition_mat = zeros((nb_struct, nb_struct))

    # save position in the canvas for each structure
    actual_position, actual_sizes = {}, {}

    # save nrj differences
    nrj_changes = {}

    # width of points
    pos_hor = 0
    crop_side = 0
    # store best change
    min_change = 0
    KT = 0.6

    for step_i, fold_step in enumerate(fast_paths):
        if len(fold_step) > 1:
            for str_i, (struct, nrj) in enumerate(fold_step):
                lprev_co = get_connected_prev(struct, fast_paths[step_i - 1])
                nrj_changes[(step_i, str_i)] = {}
                map2_struct[struct_map[struct]] = (step_i, str_i)


                for si in lprev_co:
                    prev_st, prev_nrj = fast_paths[step_i-1][si]
                    delta_nrj = nrj - prev_nrj
                    map_cur, map_prev = struct_map[struct], struct_map[prev_st]
                    transition_mat[map_cur, map_prev] = exp(delta_nrj/KT)
                    transition_mat[map_prev, map_cur] = exp(-delta_nrj/KT)

    trajectory = []
    init_pop = array([1.0] + [0.0 for _ in range(nb_struct-1)])
    for _ in range(100):
        init_pop = matmul(init_pop, transition_mat)
        init_pop /= sum(init_pop)
        trajectory += [init_pop]

    res = []
    for si, final_p in enumerate(init_pop):
        step_i, str_i = map2_struct[struct_map[struct_list[si]]]
        struct, nrj = fast_paths[step_i][str_i]
        res += [(struct_list[si], final_p, nrj)]
    res.sort(key=lambda el: el[1])
    for st, fp, nrj in res:
        print("{} {:5.3f} {:5.1f}".format(st, fp, nrj))

    trajectory = array(trajectory)
    for si, st in enumerate(struct_list):
        plt.plot(trajectory[:, si])

    plt.show()


if __name__ == '__main__':
    main()
