# AUTOGENERATED! DO NOT EDIT! File to edit: 02_transerfer_dtsek_to_dergey.ipynb (unless otherwise specified).

__all__ = ['dmp', 'remove_grouped_dtseks', 'change_dtsek_to_dollar', 'preprocess_ocr_output', 'build_pedurma_vols',
           'isNSM', 'get_first_char_idx', 'parse_double_tsek', 'adjust_next_diff', 'transfer_dtsek',
           'transfer_dtseks_to_pedurma', 'post_process', 'main']

# Cell
import unicodedata
import re
import sys

from antx.utils import optimized_diff_match_patch
from tqdm.notebook import tqdm
from config import TengyurConfig, KangyurConfig
from fastcore.parallel import parallel

# Cell
dmp = optimized_diff_match_patch()
dmp.binary_path

# Cell
def remove_grouped_dtseks(text):
    return re.sub(':{3,}', '', text)

def change_dtsek_to_dollar(text):
    return re.sub(':', config.double_tsek_sym, text)

def preprocess_ocr_output(text):
    text = remove_grouped_dtseks(text)
    if config.name == "tengyur":
        text = change_dtsek_to_dollar(text)
    return text

# Cell
def build_pedurma_vols(replace=False):
    for vol_dir in sorted(config.pedurma_output_path.iterdir()):
        vol_fn = vol_dir.parent / f"{vol_dir.name}.txt"
        if vol_dir.is_file() or vol_dir.name == '.git': continue
        if vol_fn.is_file() and not replace: continue
        vol_text = ''
        for (i, page_fn) in enumerate(sorted(vol_dir.iterdir())):
            page_text = page_fn.read_text()
            # dont't preprocess the first page, metadata
            if i: page_text = preprocess_ocr_output(page_text)
            vol_text += page_text + "\n\n\n"
        vol_fn.write_text(vol_text)

# Cell
def isNSM(char):
    # Detects nonspacing mark characters
    if unicodedata.category(char) == "Mn":
        return True
    return False

# Cell
def get_first_char_idx(text, char):
    """Return first char idx in `text` and -1 of not found

    found har idx is expanded for whitespces after the char.
    """
    is_char_found = False
    idx = -1
    for i in range(len(text)):
        if not is_char_found and text[i] == char:
            is_char_found = True
            idx = i
        elif is_char_found:
            if text[i] != ' ': return i-1
            elif i == len(text)-1: return i
    return idx

# Cell
def parse_double_tsek(text):
    double_tsek_idxs = []
    base_char_idx = 0
    for c in text:
        if c == config.double_tsek_sym:
            double_tsek_idxs.append(base_char_idx)
            continue
        base_char_idx += 1
    return double_tsek_idxs

def adjust_next_diff(i, diffs, ann_text, to_char):
    diff_mode, diff_chunk = diffs[i+1]
    # add chars till next tsek to the ann_text
    first_char_idx = get_first_char_idx(diff_chunk, to_char)
    ann_text += diff_chunk[:first_char_idx+1]
    # remove chars till next tsek from diff[i+1]
    diffs[i+1] = (diff_mode, diff_chunk[first_char_idx+1:])
    return ann_text


def transfer_dtsek(base_text, dest_text, verbose=False):
    ann_text = ''
    diffs = list(dmp.diff_main(dest_text, base_text))
    if verbose: print(diffs)
    for i in range(len(diffs)):
        if diffs[i][0] == -1:
            if config.double_tsek_sym in diffs[i][1]:
                # check for next diff adjustment
                if i < len(diffs)-1:
                    # adjust next diff[i+1] if it's first char is NSM
                    if isNSM(diffs[i+1][1][0]):
                        ann_text = adjust_next_diff(i, diffs, ann_text, config.tsek)

                    # adjust next diff[i+1] if it's first char in tsek
                    elif diffs[i+1][1][0] == config.tsek:
                        ann_text = adjust_next_diff(i, diffs, ann_text, config.tsek)

                    # adjust next diff[i+1] if it's first char in shed
                    elif diffs[i+1][1][0] == config.shed:
                        ann_text = adjust_next_diff(i, diffs, ann_text, config.shed)

                    # adjust next diff[i+1] if its first char is line return
                    elif diffs[i+1][1][0] == '\n':
                        ann_text = adjust_next_diff(i, diffs, ann_text, '\n')

                if len(diffs[i][1]) == 1:
                    ann_text += diffs[i][1]
                else:
                    ann_text += '$'
        else:
            if verbose: print(diffs[i])
            ann_text += diffs[i][1]
    double_tsek_idxs = parse_double_tsek(ann_text)
    print(f'\t- Transferred {len(double_tsek_idxs)} out of {dest_text.count(config.double_tsek_sym)}')
    return double_tsek_idxs, ann_text

# Cell
def _run(fns):
    for pedurma_base_fn, ocr_dtsek_fn in fns:
        pedurma_dtsek_dir = ocr_dtsek_fn.parent.parent / "pedurma_dtseks"
        pedurma_dtsek_fn = pedurma_dtsek_dir / pedurma_base_fn.name
        print("Transfering ", pedurma_dtsek_fn.stem)
        _, pedurma_dtsek = transfer_dtsek(pedurma_base_fn.read_text(), ocr_dtsek_fn.read_text())
        pedurma_dtsek_fn.write_text(pedurma_dtsek)

def transfer_dtseks_to_pedurma(replace=False):
    def _filter_completed(fns):
        result = []
        for (pedurma_base_fn, ocr_dtsek_fn) in fns:
            pedurma_dtsek_fn = pedurma_dtsek_dir / pedurma_base_fn.name
            if pedurma_dtsek_fn.is_file():
                print(pedurma_dtsek_fn.stem, " completed")
                continue
            result.append((pedurma_base_fn, ocr_dtsek_fn))
        return result


    "Returns pedurma base and ocr dobule tsek"
    pedurma_base_dir = config.op_pechas_path / config.p_pecha_id / f"{config.p_pecha_id}.opf" / "base"
    pecha_base_fns = sorted([fn for fn in pedurma_base_dir.iterdir() if config.name == "tengyur" and fn.stem != "v052"])
    ocr_dtsek_fns = sorted([fn for fn in config.pedurma_output_path.iterdir() if fn.is_file()])

    pedurma_dtsek_dir = config.pedurma_output_path.parent / "pedurma_dtseks"
    pedurma_dtsek_dir.mkdir(exist_ok=True, parents=True)
    fns = zip(pecha_base_fns, ocr_dtsek_fns)
    if not replace: fns = _filter_completed(fns)
    _run(fns)

# Cell
def post_process():
    def _cleanup_dtseks(text):
        text = vol_fn.read_text()
        text = text.replace('$:', ':')
        text = text.replace(':$', ':')
        text = text.replace('$', ':')
        text = text.replace('::', ':')
        return text

    pedurma_dtsek_dir = config.pedurma_output_path.parent / "pedurma_dtseks"
    for vol_fn in pedurma_dtsek_dir.iterdir():
        print(f"post processing {vol_fn.stem} ...")
        text = vol_fn.read_text()
        text = _cleanup_dtseks(text)
        vol_fn.write_text(text)

# Cell
def main():
    print("[INFO] building pedurma vols ...")
    build_pedurma_vols()
    print("[INFO] transfering dtesks to pedurma ...")
    transfer_dtseks_to_pedurma()
    print("[INFO] post processing ...")
    post_process()

# Cell
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "k":
        config = KangyurConfig()
    else:
        config = TengyurConfig()
    main()