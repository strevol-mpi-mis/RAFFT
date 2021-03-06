"""Utils functions for the structure prediction
"""

from numpy import array, flip, concatenate
from numpy import sum as npsum
from scipy.signal import convolve
from RNA import fold_compound, md

class Glob_parms:
    "Store all non redundant information"

    def __init__(self, sequence, nb_mode, max_stack, max_branch, min_hp,
                 min_nrj, traj, temp, gc_wei, au_wei, gu_wei):
        self.sequence, self.temp, self.nb_mode, = sequence, temp, nb_mode,
        self.max_stack, self.min_hp, self.min_nrj = max_stack, min_hp, min_nrj
        self.traj, self.temp, self.max_branch = traj, temp, max_branch
        self.gc_wei, self.au_wei, self.gu_wei = gc_wei, au_wei, gu_wei
        self.model = md()
        self.model.temperature = temp
        self.len_seq = len(sequence)
        self.seq_comp = fold_compound(sequence, self.model)


class Node:
    "unpaired regions"

    def __init__(self, forward, backward, unpaired_pos):
        self.forward, self.backward = forward, backward
        self.pos_list = unpaired_pos


class Structure:
    "A structure is modeled as a tree; in bfs, the tree is a list of nodes"

    def __init__(self, node_list, pair_list):
        self.node_list = node_list
        self.energy = 0.0
        self.pair_list = pair_list
        self.str_struct = ""


def dot_bracket(pair_list, len_seq, SEQ=None):
    """convert the list of BPs into a dot bracket notation
    """
    str_struct = list("."*len_seq)
    for pi, pj in pair_list:
        # if SEQ is not None:
        #     print(SEQ[pi], SEQ[pj])
        str_struct[pi], str_struct[pj] = "(", ")"
    return "".join(str_struct)


def paired_positions(structure):
    "return a list of pairs (paired positions)"
    # save open bracket in piles
    pile_reg, pile_pk = [], []
    pairs = []
    for i, sstruc in enumerate(structure):
        if sstruc in ["<", "("]:
            pile_reg += [i]
        elif sstruc == "[":
            pile_pk += [i]
        elif sstruc in [">", ")"]:
            pairs += [(pile_reg.pop(), i)]
        elif sstruc == "]":
            pairs += [(pile_pk.pop(), i)]
    return pairs


def prep_sequence(sequence, gc_wei=1.0, au_wei=1.0, gu_wei=1.0):
    """Encode the sequence into two mirror strands
    """
    ENCODING = {"A": [1., 0, 0, 0], "G": [0, 1., 0, 0], "C": [0, 0, 1., 0], "U": [0, 0, 0, 1.], "N": [0, 0, 0, 0]}
    CENCODING = {"A": [0, 0, 0, au_wei], "G": [0, 0, gc_wei, gu_wei], "C": [0, gc_wei, 0, 0], "U": [au_wei, gu_wei, 0, 0], "N": [0, 0, 0, 0]}
    CAN_PAIR = [('A', 'U'), ('U', 'A'), ('G', 'C'), ('C', 'G'), ('G', 'U'), ('U', 'G')]

    # the foward strand use the normal encoding
    ENCODE = lambda s: array([ENCODING[n] for n in s])
    # take the complementary nucleotides
    C_ENCODE = lambda s: array([CENCODING[n] for n in s])

    e_seq = ENCODE(sequence).T
    c_seq = flip(C_ENCODE(sequence).T, axis=1)
    return e_seq, c_seq


def slice_string(seq):
    "return a list of overlapping slices"
    len_s = len(seq)
    return [tuple(seq[i: i+2]) for i in range(len_s-1)]


def prep_sequence_stacks(sequence):
    """Encode the sequence into two mirror strands
    """
    NUC = ['A', 'G', 'C', 'U']
    cc = {'A': 'U', 'G': 'C', 'C': 'G', 'U': 'A'}
    pairs = [(aa, aa_) for aa in NUC for aa_ in NUC]
    ENCODING = {p: [(1.0 if i == pi else 0.0) for i in range(16)] for pi, p in enumerate(pairs)}

    sliced_seq = slice_string(sequence)
    # rev_sliced_seq = slice_string("".join([cc[el] for el in sequence[::-1]]))
    rev_sliced_seq = slice_string("".join([cc[el] for el in sequence[::-1]]))

    # the foward strand use the normal encoding
    ENCODE = lambda s: array([ENCODING[n] for n in s])
    # take the complementary nucleotides
    C_ENCODE = lambda s: array([ENCODING[n] for n in s])

    e_seq = ENCODE(sliced_seq).T
    c_seq = C_ENCODE(rev_sliced_seq).T
    return e_seq, c_seq


def seq_conv(seq, cseq):
    "Compute the autocorrelation for the 4 components then sum per position"
    cseq = flip(cseq, axis=1)
    cor_ = []
    for i in range(seq.shape[0]):
        # the convolution routine will use the fft if faster
        cor_ += [convolve(seq[i, ], cseq[i, ])]
    return npsum(array(cor_), axis=0)


def auto_cor(seq, cseq, pad=1.0):
    """Compute the auto correlation between the two strands
    """
    len_seq = seq.shape[1]
    cor = seq_conv(seq, cseq)
    norm = [(el+pad) for el in list(range(len_seq)) + list(range(len_seq-1))[::-1]]
    cor_l = [[i, c] for i, c in enumerate(cor/norm)]
    return cor_l


def eval_one_struct(pair_list, glob_parms):
    "eval individual loop moves"
    dot_struct = dot_bracket(pair_list, glob_parms.len_seq)
    return glob_parms.seq_comp.eval_structure(dot_struct)


def get_outer_loop(seq, cseq, max_i, max_j, max_bp, pos_list, len_seq):
    oseq = concatenate((seq[:, :max_i-max_bp+1], seq[:, max_j+max_bp:]), axis=1)
    ocseq = concatenate((cseq[:, :len_seq - (max_j+max_bp)], cseq[:, len_seq-(max_i-max_bp+1):]), axis=1)
    pos_list_2 = pos_list[:max_i-max_bp+1] + pos_list[max_j+max_bp:]
    return oseq, ocseq, [el for el in pos_list_2]


def get_inner_loop(seq, cseq, max_i, max_j, max_bp, pos_list, len_seq):
    oseq = seq[:, max_i+1:max_j]
    ocseq = cseq[:, len_seq-max_j:len_seq-max_i-1]
    pos_list_2 = pos_list[max_i+1:max_j]
    return oseq, ocseq, [el for el in pos_list_2]


def merge_pair_list(pair_1, pair_2):
    "merge pair_2 into pair_1"
    for el in set(pair_2) - set(pair_1):
        pair_1 += [el]


def read_fasta(infile):
    results = {}
    for l in open(infile):
        if l.startswith(">"):
            name = l.strip()[1:]
            results[name] = ""
        else:
            results[name] += l.strip()
    return results


def parse_rafft_output(infile):
    results = []
    with open(infile) as rafft_out:
        seq = rafft_out.readline().strip()
        for l in rafft_out:
            if l.startswith("# --"):
                results += [[]]
            else:
                str_struct, nrj = l.strip().split()
                struct = Structure([], [])
                struct.str_struct = str_struct
                struct.energy = float(nrj)
                results[-1] += [struct]
    return results, seq
