"""HCL scanner: finds the top-level blocks of a .tf file and the attributes of each.

We do not need a full HCL parser, only enough to answer questions like "which resources does this file declare, with
which attributes?". The approach:

  1. Make two copies of the text where comments, and then strings, are replaced by spaces (`_mask`). That way a brace
     or a keyword inside a comment or a string can never be mistaken for code.
  2. Find the start of each block with a regular expression (`BLOCK_RE`) and walk forward counting braces to find where
     it ends (`parse`).
  3. Read the `key = value` lines of each block body (`_attrs`).

Deliberately shallow: a block must start in column 0, which is how `terraform fmt` leaves them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# The first line of a block. Matches e.g.   resource "aws_s3_bucket" "this" {
#                                           variable "name" {
# group 1 = the kind, group 2 = all the quoted labels.
BLOCK_RE = re.compile(
    r'^(resource|data|variable|output|module)[ \t]+((?:"[^"\n]*"[ \t]*)+)\{', re.MULTILINE
)
# A double-quoted string, allowing escaped quotes inside:  "a \" b"
_STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"')
# The start of a heredoc:  <<EOT   or   <<-EOT   (the text up to a line that is just EOT is not code)
HEREDOC_RE = re.compile(r"<<-?([A-Za-z_][A-Za-z0-9_]*)\n")


@dataclass
class Block:
    """One HCL block (resource, data, variable, output or module) found in a .tf file."""
    kind: str                 # "resource", "data", "variable", "output" or "module"
    labels: List[str]         # the quoted words after the kind: ["aws_s3_bucket", "this"]
    body: str                 # everything between the braces, comments removed
    file: str                 # path of the .tf file, relative to the repository
    line: int                 # line where the block starts
    attrs: Dict[str, str] = field(default_factory=dict)  # top-level `key = value` pairs of the body

    @property
    def type(self) -> str:
        """First label of the block (the resource type for a resource)."""
        return self.labels[0] if self.labels else ""

    @property
    def name(self) -> str:
        """Last label of the block: its own name."""
        return self.labels[-1] if self.labels else ""

    @property
    def address(self) -> str:
        """How Terraform names it: `type.name` for a resource, `kind.name` otherwise."""
        if self.kind == "resource":
            return "{}.{}".format(self.labels[0], self.labels[1])
        return "{}.{}".format(self.kind, self.name)


def _mask(text: str) -> Tuple[str, str]:
    """Return two copies of `text` with the same length and the same line breaks:

      * without_comments: comments are replaced by spaces;
      * without_strings:  comments AND the content of strings are replaced by spaces.

    Keeping the length identical means a position found in one copy points at the same place in the original text."""
    length = len(text)
    without_comments = list(text)
    without_strings = list(text)

    def blank_out(chars: List[str], start: int, end: int) -> None:
        # Replace every character by a space, except line breaks, so line numbers stay correct.
        for position in range(start, end):
            if chars[position] != "\n":
                chars[position] = " "

    i = 0
    while i < length:
        char = text[i]

        if char == "#" or text.startswith("//", i):
            # A line comment: blank everything up to the end of the line.
            end = text.find("\n", i)
            end = length if end == -1 else end
            blank_out(without_comments, i, end)
            blank_out(without_strings, i, end)
            i = end

        elif text.startswith("/*", i):
            # A block comment: blank everything up to and including the closing */
            end = text.find("*/", i + 2)
            end = length if end == -1 else end + 2
            blank_out(without_comments, i, end)
            blank_out(without_strings, i, end)
            i = end

        elif char == '"':
            # A string: find its closing quote (a backslash escapes the next character) and blank the content, but only in
            # the "without strings" copy. The text of the string is still real code for the other copy.
            j = i + 1
            while j < length and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            blank_out(without_strings, i + 1, j)
            i = j + 1

        elif text.startswith("<<", i) and HEREDOC_RE.match(text, i):
            # A heredoc: its lines are text, not code, up to a line that holds only the marker (EOT).
            heredoc = HEREDOC_RE.match(text, i)
            assert heredoc is not None   # the `elif` above just matched it
            closing_line = re.compile(r"^[ \t]*%s[ \t]*$" % re.escape(heredoc.group(1)), re.MULTILINE).search(text, heredoc.end())
            end = closing_line.end() if closing_line else length
            blank_out(without_comments, heredoc.end(), end)
            blank_out(without_strings, heredoc.end(), end)
            i = end

        else:
            i += 1

    return "".join(without_comments), "".join(without_strings)


def _find_closing_brace(code: str, open_position: int) -> Optional[int]:
    """Position of the `}` that closes the `{` at `open_position`, counting nested braces. None if it never closes."""
    depth = 0
    for position in range(open_position, len(code)):
        if code[position] == "{":
            depth += 1
        elif code[position] == "}":
            depth -= 1
            if depth == 0:
                return position
    return None


def parse(text: str, file: str) -> List[Block]:
    """Find the top-level blocks of a .tf file and the attributes of each, ignoring comments and strings."""
    without_comments, without_strings = _mask(text)
    blocks: List[Block] = []

    for header in BLOCK_RE.finditer(without_comments):
        open_position = header.end() - 1                     # the "{" that ends the header line
        close_position = _find_closing_brace(without_strings, open_position)
        if close_position is None:
            continue                                         # an unbalanced block: skip it rather than guess

        labels = re.findall(r'"([^"\n]*)"', header.group(2))
        body = without_comments[open_position + 1:close_position]
        blocks.append(Block(
            kind=header.group(1),
            labels=labels,
            body=body,
            file=file,
            line=text.count("\n", 0, header.start()) + 1,    # lines before the header, plus one
            attrs=_attrs(body),
        ))
    return blocks


def _attrs(body: str) -> Dict[str, str]:
    """The top-level `key = value` attributes of a block body.

    A value may continue over several lines while a bracket is open, e.g.
        tags = merge(var.extra_tags,
                     local.mandatory_tags)
    Nested blocks (`lifecycle { ... }`) are not attributes and are skipped."""
    attributes: Dict[str, str] = {}
    depth = 0                          # how many {, [ or ( are open right now
    current_key: Optional[str] = None  # the attribute whose value we are still reading
    current_lines: List[str] = []      # the lines of that value

    def finish_current() -> None:
        if current_key is not None:
            attributes[current_key] = "\n".join(current_lines).strip()

    for line in body.splitlines():
        stripped = line.strip()

        if depth == 0:
            assignment = re.match(r"^([A-Za-z_][\w-]*)\s*=\s*(.*)$", stripped)
            if assignment:
                # A new `key = value` line: store the previous attribute and start this one.
                finish_current()
                current_key, current_lines = assignment.group(1), [assignment.group(2)]
            elif current_key is not None and not stripped:
                continue                                      # a blank line after a value: nothing to do
            elif current_key is not None:
                # A line that is not an assignment (for example the start of a nested block): the value has ended.
                finish_current()
                current_key, current_lines = None, []
        elif current_key is not None:
            current_lines.append(stripped)                    # inside brackets: the value continues on this line

        # Update the bracket depth from this line, ignoring brackets that sit inside strings.
        without_strings = _STRING_RE.sub('""', line)
        opened = sum(without_strings.count(char) for char in "{[(")
        closed = sum(without_strings.count(char) for char in "}])")
        depth = max(depth + opened - closed, 0)

    finish_current()
    return attributes
