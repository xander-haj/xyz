"""
Shared helpers for overworld dump generation.
"""

import json
import os
import re


def extract_array(source, name):
  pattern = re.compile(r"\b%s\b\s*(?:\[[^\]]*\]\s*)*=\s*\{" % re.escape(name))
  match = pattern.search(strip_comments_preserve_length(source))
  if not match:
    raise Exception("Unable to find source array %s" % name)
  start = match.end() - 1
  depth = 0
  for index in range(start, len(source)):
    char = source[index]
    if char == "{":
      depth += 1
    elif char == "}":
      depth -= 1
      if depth == 0:
        return source[start:index + 1]
  raise Exception("Source array %s initializer is not balanced" % name)


def parse_matrix(block):
  rows = []
  clean = strip_comments(block)
  for match in re.finditer(r"\{([^{}]*)\}", clean):
    row = parse_numbers(match.group(1))
    if row:
      rows.append(row)
  return rows


def parse_numbers(block):
  matches = re.findall(r"-?0x[0-9a-fA-F]+|-?\d+", strip_comments(block))
  return [parse_number(token) for token in matches]


def parse_number(token):
  if token.startswith("-0x"):
    return -int(token[3:], 16)
  if token.startswith("0x"):
    return int(token[2:], 16)
  return int(token, 10)


def strip_comments(text):
  return re.sub(r"//.*?$", "", re.sub(r"/\*.*?\*/", "", text, flags=re.S), flags=re.M)


def strip_comments_preserve_length(text):
  def spaces(match):
    return re.sub(r"[^\n]", " ", match.group(0))
  return re.sub(r"//.*?$", spaces, re.sub(r"/\*.*?\*/", spaces, text, flags=re.S), flags=re.M)


def read_text(path):
  with open(path, "r") as file:
    return file.read()


def uint16le(values):
  result = bytearray()
  for value in values:
    result.extend(int(value).to_bytes(2, "little"))
  return bytes(result)


def write_bytes(path, data):
  ensure_dir(os.path.dirname(path))
  with open(path, "wb") as file:
    file.write(data)


def write_json(path, data):
  ensure_dir(os.path.dirname(path))
  with open(path, "w") as file:
    json.dump(data, file, indent=2, sort_keys=True)
    file.write("\n")


def ensure_dir(path):
  if path:
    os.makedirs(path, exist_ok=True)
