# AUTOGENERATED! DO NOT EDIT! File to edit: 01_extract_dtsek_from_image.ipynb (unless otherwise specified).

__all__ = ['get_templates', 'mtm', 'get_ocr_output', 'get_symbol', 'get_full_text_annotations', 'resize_boxes',
           'cls_box_into_line', 'find_double_tsek_bf', 'compute_iou', 'get_double_tsek_idx', 'put_whitespaces',
           'rm_running_head', 'rm_noise', 'postprocess', 'str_insert', 'add_double_tsek', 'extract_double_tsek_vol',
           'get_double_tsek_vol_by_pages', 'main']

# Cell
from collections import defaultdict
import cv2
import gzip
import json
import math
from pathlib import Path
import sys
import re

from concurrent.futures import ProcessPoolExecutor


from MTM import matchTemplates, drawBoxesOnRGB
import numpy as np
from config import TengyurConfig, KangyurConfig

# Cell
def get_templates(path):
    templates = []
    for p in Path(path).iterdir():
        if not p.name.endswith('.png'): continue
        templates.append((p.stem, cv2.imread(str(p))))
    return templates

def mtm(image, templates, show=False, th=0.9):
    if isinstance(image, (str, Path)):
        image = cv2.imread(str(image))
    matches = []
    try:
        hits = matchTemplates(templates, image, score_threshold=th, method=cv2.TM_CCOEFF_NORMED, maxOverlap=0.3)
        for x, y, w, h in list(hits['BBox']):
            matches.append([x, y, x+w, y+h])
        if show: image = drawBoxesOnRGB(image, hits, boxThickness=5, boxColor=(255,0,0))
    except KeyError as ex:
        if ex.args[0] == 'Score':
            print('\t- double tsek not found !')
            return matches

    print(f'\t- no. of double tsek detected: {len(matches)}')
    if show:
        plot(image, sz=(15, 15))

    return matches

# Cell
def get_ocr_output(path):
    imagegroup, img_fn = path.parts[-2:]
    res_fn = config.ocr_output_path/imagegroup/f'{img_fn.split(".")[0]}.json.gz'
    return json.load(gzip.open(str(res_fn), 'rb'))

def get_symbol(response):
    if 'fullTextAnnotation' not in response:
        return None, None
    for page in response['fullTextAnnotation']['pages']:
        for block in page['blocks']:
            for paragraph in block['paragraphs']:
                for word in paragraph['words']:
                    for symbol in word['symbols']:
                        char = symbol['text']
                        v = symbol['boundingBox']['vertices']
                        x1, y1 = v[0].get('x', 0), v[0].get('y', 0)
                        x2, y2 = v[2].get('x', 0), v[2].get('y', 0)
                        box = [x1, y1, x2, y2]
                        yield char, box

def get_full_text_annotations(response):
    boxes, text = [], ''
    for char, box in get_symbol(response):
        if not char and not box:
            break
        text += char
        boxes.append(box)
    return boxes, text

def resize_boxes(boxes, old_size):
    "`boxes` are in top-right and bottom-left coord system."
    h, w = old_size[:2]
    h_scale = config.img_size[0]/h
    w_scale = config.img_size[1]/w
    result = []
    for box in boxes:
        # adjust the box
        box[0] *= w_scale
        box[1] *= h_scale
        box[2] *= w_scale
        box[3] *= h_scale
        box = list(map(int, box))
        result.append(box)
    return result

# Cell
def cls_box_into_line(boxes, th=20):
    lines = []
    line = []
    prev_y1 = boxes[0][1]
    for box in boxes:
        if abs(box[1] - prev_y1) < th:
            line.append(box)
        else:
            lines.append(line)
            line = []
            line.append(box)
        prev_y1 = box[1]
    else:
        if line: lines.append(line)
    return lines

# Cell
def find_double_tsek_bf(matched_box, boxes, th=20):
    box_lines = cls_box_into_line(boxes)
    pos = 0
    prev_x1 = 0
    for box_line in box_lines:
        if abs(matched_box[1] - box_line[0][1]) < th:
            for i, box in enumerate(box_line):
                if matched_box[0] > prev_x1 and matched_box[0] < box[0]:
                    pos += i-1
                    return pos
        pos += len(box_line)


def compute_iou(box_arr1, box_arr2):
    x11, y11, x12, y12 = np.split(box_arr1, 4, axis=1)
    x21, y21, x22, y22 = np.split(box_arr2, 4, axis=1)

    xA = np.maximum(x11, np.transpose(x21))
    yA = np.maximum(y11, np.transpose(y21))
    xB = np.minimum(x12, np.transpose(x22))
    yB = np.minimum(y12, np.transpose(y22))
    interArea = np.maximum((xB - xA + 1), 0) * np.maximum((yB - yA + 1), 0)
    boxAArea = (x12 - x11 + 1) * (y12 - y11 + 1)
    boxBArea = (x22 - x21 + 1) * (y22 - y21 + 1)
    iou = interArea / (boxAArea + np.transpose(boxBArea) - interArea)

    return iou


def get_double_tsek_idx(image_path, templates, deskew=False, show_boxes=False):
    # load, deskew and resize the image
    image = cv2.imread(str(image_path))
    old_size = image.shape
    if deskew: image = image_deskew(image)
    image = cv2.resize(image, (config.img_size[1], config.img_size[0]))

    # find the double tsek boxes
    matches = mtm(image, templates)

    # Get ocr boxes
    try:
        response = get_ocr_output(image_path)
    except FileNotFoundError:
        return [], ""
    boxes, text = get_full_text_annotations(response)
    if not matches or not boxes: return [], text
    boxes = resize_boxes(boxes, old_size)

    # find double tsek char index
    iou_matrix = compute_iou(np.array(matches), np.array(boxes))
    if show_boxes: plot_boxes(image, [boxes, matches])
    idxs = list(np.argmax(iou_matrix, axis=1))
    if 0 in idxs:
        undetected_box_idx = idxs.index(0)
        undetected_box_char_idx = find_double_tsek_bf(matches[undetected_box_idx], boxes)
        if undetected_box_char_idx:
            idxs[undetected_box_idx] = undetected_box_char_idx
        else:
            idxs.pop(undetected_box_idx)
    idxs.sort()
    return idxs, text

# Cell
def put_whitespaces(text):
    result = ''
    for chunk in text.split('།'):
        if chunk:
            result += chunk + '། '
        else:
            result += '།'
    return result

# Cell
def rm_running_head(text):
    r_head_end_idx = text.find('༡')
    if r_head_end_idx >= 0  and r_head_end_idx < 500:
        return text[r_head_end_idx+1:]
    else:
        return text[text.find('།')+1:]

def rm_noise(text):
    'remove numbers and etc'
    text = re.sub(f'\d+', '', text)
    for r in ['=', '|', '“', '”', ']', '）', ')', '》', '>', '©', '–', '-', '༸', ('་ི', '་')]:
        if isinstance(r, tuple):
            text = text.replace(r[0], r[1])
        else:
            text = text.replace(r, '')
    return text

def postprocess(text):
    text = rm_running_head(text)
    text = rm_noise(text)
    for f, t in [('$་','་$'), ('$།', '།$'), ('།་$', '།$')]:
        text = text.replace(f, t)
    text = put_whitespaces(text)
    return text

def str_insert(text, idx, char):
    text = text[:idx] + char + text[idx:]
    return text

def add_double_tsek(text, idxs):
    for i, idx in enumerate(idxs):
        text = str_insert(text, idx+i, config.double_tsek_sym)
    return text

def extract_double_tsek_vol(vol_id, image_group_path):
    ann_text_fn = config.pedurma_output_path/f'{vol_id}.txt'
    if ann_text_fn.is_file():
        return
    ann_text_pages = []
    for i, path in enumerate(sorted((image_group_path).iterdir()), 1):
        print(f'[INFO] {i+1} - Processing {path.stem} ...')

        # cache page dtsek output
        dt_vol_output_dir = config.pedurma_output_path/image_group_path.name
        dt_vol_output_dir.mkdir(parents=True, exist_ok=True)
        dt_page_output_fn = dt_vol_output_dir / f"{path.stem}.txt"
        if dt_page_output_fn.is_file():
            continue

        idxs, text = get_double_tsek_idx(path, templates)
        dt_page_output = postprocess(add_double_tsek(text, idxs))
        dt_page_output_fn.write_text(dt_page_output)

# Cell
def get_double_tsek_vol_by_pages(path, start, end, engine):
    for i, path in enumerate(sorted((path).iterdir()), 1):
        if i <  start: continue
        if i > end: break
        # speed up
        ann_page_fn = config.output_tmp_path/f'{path.stem}-ann.txt'
        if ann_page_fn.is_file():
            ann_page = ann_page_fn.read_text()
            if engine == 'diff':
                yield '', ann_page, path.stem
            else:
                base_page = ann_page.replace(config.double_tsek_sym, '')
                yield base_page, ann_page, path.stem

        print(f'[INFO] {i+1} - Processing {path.name} ...')
        idxs, text = get_double_tsek_idx(path, templates)
        ann_page = postprocess(add_double_tsek(text, idxs))
        ann_page_fn.write_text(ann_page)
        if engine == 'diff':
            yield '', ann_page, path.stem
        else:
            base_page = ann_page.replace(config.double_tsek_sym, '')
            yield base_page, ann_page, path.stem

# Cell
def main():
    for i, img_group_path in enumerate(sorted(config.images_path.iterdir()), 1):
        extract_double_tsek_vol(f"v{i:03}", img_group_path)

# Cell
if __name__ == "__main__":
    if sys.argv == "k":
        config = KangyurConfig()
    else:
        config = TengyurConfig()
    templates = get_templates(config.template_path); len(templates)
    main()