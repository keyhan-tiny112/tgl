import re
from typing import List, Tuple, Optional, Dict, Any, Union

__all__ = ["load", "dump"]
__license__ = "Apache-v2"


# --- Helper Classes and Functions (Assume these are defined elsewhere) ---
class TGLNode:
    def __init__(self, name: str, attrs: Optional[Dict[str, Any]] = None):
        self.name = name
        self.attrs = attrs if attrs is not None else {}
        self.vars: Dict[str, Any] = {}
        self.children: List['TGLNode'] = []

    def to_dict(self, sample: bool = True):
        if not sample:
            # ساختار اصلی و درختی (برای دیباگ و سریالایزیشن کامل)
            return {
                "name": self.name,
                "attrs": self.attrs,
                "vars": self.vars,
                "children": [child.to_dict(sample=False) for child in self.children]
            }
        
        # ساختار مسطح (Flattened) برای استفاده در Flux
        result = {}
        counts = {}

        # 1. افزودن اتریبیوت‌ها با پیشوند @
        for key, value in self.attrs.items():
            result[f"@{key}"] = value

        # 2. افزودن متغیرها
        for key, value in self.vars.items():
            result[key] = value

        # 3. افزودن فرزندان (نودهای تو در تو)
        for child in self.children:
            base_name = child.name
            final_name = base_name
            
            # مدیریت نودهای همنام (Auto-Enumeration)
            if base_name in counts:
                counts[base_name] += 1
                final_name = f"{base_name}-{counts[base_name]}"
            else:
                counts[base_name] = 1
            
            # تبدیل بازگشتی فرزند
            result[final_name] = child.to_dict(sample=True)

        return result
    
    @classmethod
    def _format_value(cls, value: Any) -> str:
        if isinstance(value, bool): return "true" if value else "false"
        elif isinstance(value, (int, float)): return repr(value)
        elif isinstance(value, str): return '"' + value.replace('"', '\\"') + '"'
        elif isinstance(value, list):
            return "[" + ", ".join(cls._format_value(v) for v in value) + "]"
        elif isinstance(value, dict):
            items = []
            for k, v in value.items():
                formatted_key = cls._format_value(k)
                formatted_value = cls._format_value(v)
                items.append(f"{formatted_key}: {formatted_value}")
            return "{ " + ", ".join(items) + " }"
        raise TypeError(f"Unsupported value type: {type(value).__name__}")

    @classmethod
    def _format_attrs(cls, attrs: Dict[str, Any]) -> str:
        if not attrs: return ""
        parts = [f"{k} = {cls._format_value(v)}" for k, v in sorted(attrs.items())]
        return f"({', '.join(parts)})"

    def to_tgl(self, indent_level: int = 0, indent_size: int = 2) -> str:
        lines = []
        indent_spaces = " " * (indent_level * indent_size)
        
        # 1. Header (اگر ریشه است بدون |، اگر فرزند است با |)
        header = f"[{self.name}]{self._format_attrs(self.attrs)}"
        if indent_level == 0:
            lines.append(f"{indent_spaces}{header}")
        else:
            lines.append(f"{indent_spaces}| {header}")

        # 2. Vars
        for key, value in sorted(self.vars.items()):
            var_indent = " " * ((indent_level + 1) * indent_size)
            lines.append(f"{var_indent}| {key} = {self._format_value(value)}")

        # 3. Children
        for child in self.children:
            lines.append(child.to_tgl(indent_level + 1, indent_size))
            # بستن بلاک فرزند
            lines.append(" " * ((indent_level + 1) * indent_size) + ";")

        return "\n".join(lines)

    def __str__(self):
        # با فراخوانی متد اصلی، در نهایت ریشه رو می‌بندیم
        return self.to_dict() + "\n;"

class TGLParseError(Exception):
    def __init__(self, message: str, line: int, raw_line: str):
        super().__init__(
            f"""
            [line {line}] {message}
            >>> {raw_line}
            """
        )
        self.line = line
        self.raw_line = raw_line

def dump(ast: Dict[str, Union[List, Dict, str, int, float, bool]], indent_level: int = 0, indent_size: int = 2) -> str:
    lines = []
    indent_spaces = " " * (indent_level * indent_size)
    base_header_num: int = 0
    
    # 1. Header (اگر ریشه است بدون |، اگر فرزند است با |)
    header = f"[{ast['name']}]{TGLNode._format_attrs(ast['attrs'])}"
    if indent_level == 0:
        lines.append(f"{indent_spaces}{header}")
    else:
        lines.append(f"{indent_spaces}| {header}")

    # 2. Vars
    for key, value in sorted(ast['vars'].items()):
        var_indent = " " * ((indent_level + 1) * indent_size)
        lines.append(f"{var_indent}| {key} = {TGLNode._format_value(value)}")

    # 3. Children
    for child in ast['children']:
        lines.append(dump(child, indent_level + 1, indent_size))
        # بستن بلاک فرزند
        lines.append(" " * ((indent_level + 1) * indent_size) + ";")

    return "\n".join(lines)

def _escape_string_content(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
         .replace('"', '\\"')
         .replace("\n", "\\n")
    )


def _starts_multiline_string(line: str) -> bool:
    if "=" not in line:
        return False
    _, rhs = line.split("=", 1)
    return rhs.lstrip().startswith('"""')


def _merge_multiline_string(lines: list[str]) -> str:
    first = lines[0]

    prefix, sep, rest = first.partition('"""')
    if not sep:
        return first

    content_parts = []

    # اگر بعد از """ در همان خط چیزی آمده باشد
    if rest:
        # اگر همان خط بسته هم شده باشد
        if '"""' in rest:
            before_end, _, _ = rest.partition('"""')
            content_parts.append(before_end)
        else:
            content_parts.append(rest)

    # اگر closing delimiter در همان خط اول نبود
    if '"""' not in rest:
        for line in lines[1:]:
            if '"""' in line:
                before_end, _, _ = line.partition('"""')
                content_parts.append(before_end)
                break
            content_parts.append(line)

    raw_content = "\n".join(content_parts)
    escaped = _escape_string_content(raw_content)

    return f'{prefix}"{escaped}"'


def _is_inside_string(line: str, index: int) -> bool:
    in_string = False
    escape = False

    for i, ch in enumerate(line):
        if i >= index:
            break

        if escape:
            escape = False
            continue

        if ch == "\\":
            escape = True
            continue

        if ch == '"':
            in_string = not in_string

    return in_string


def _count_brackets_outside_strings(s: str) -> tuple[int, int]:
    square = 0
    curly = 0
    in_string = False
    escape = False
    i = 0

    while i < len(s):
        ch = s[i]

        if escape:
            escape = False
            i += 1
            continue

        if ch == "\\":
            escape = True
            i += 1
            continue

        if ch == '"':
            in_string = not in_string
            i += 1
            continue

        if not in_string:
            if ch == "[":
                square += 1
            elif ch == "]":
                square -= 1
            elif ch == "{":
                curly += 1
            elif ch == "}":
                curly -= 1

        i += 1

    return square, curly


def _starts_multiline_bracket_value(line: str) -> bool:
    if "=" not in line:
        return False

    _, rhs = line.split("=", 1)
    rhs = rhs.lstrip()

    if not rhs:
        return False

    if rhs.startswith("[") or rhs.startswith("{"):
        sq, cu = _count_brackets_outside_strings(rhs)
        return sq > 0 or cu > 0

    return False


def _merge_multiline_brackets(lines: list[str]) -> str:
    if not lines:
        return ""

    first = lines[0]
    prefix, eq, rhs = first.partition("=")
    if not eq:
        return first

    pieces = [rhs.strip()]

    for line in lines[1:]:
        pieces.append(line.strip())

    merged_value = " ".join(piece for piece in pieces if piece)
    return f"{prefix}{eq} {merged_value}"


def normalize_multiline_values(text: str) -> str:
    lines = text.splitlines()
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # multiline string
        if _starts_multiline_string(line):
            collected = [line]
            i += 1

            # اگر در همان خط اول بسته شده بود
            if line.count('"""') >= 2:
                result.append(_merge_multiline_string(collected))
                continue

            while i < len(lines):
                collected.append(lines[i])
                if '"""' in lines[i]:
                    break
                i += 1

            result.append(_merge_multiline_string(collected))
            i += 1
            continue

        # multiline list / dict
        if _starts_multiline_bracket_value(line):
            collected = [line]
            _, rhs = line.split("=", 1)
            sq, cu = _count_brackets_outside_strings(rhs)

            i += 1
            while i < len(lines) and (sq > 0 or cu > 0):
                collected.append(lines[i])
                dsq, dcu = _count_brackets_outside_strings(lines[i])
                sq += dsq
                cu += dcu
                i += 1

            result.append(_merge_multiline_brackets(collected))
            continue

        result.append(line)
        i += 1

    return "\n".join(result)

BLOCK_COMMENT_PATTERN = re.compile(r"<--.*?-->", re.DOTALL)

def remove_block_comments(text: str) -> str:
    """
    Remove all block comments of the form <-- ... --> from the text.
    Non-nested. Uses non-greedy matching.
    """
    return re.sub(BLOCK_COMMENT_PATTERN, "", text)

def _strip_comment(line: str) -> str:
    # اول، چک کن که آیا خط فقط یک کامنت -- است؟
    stripped = line.lstrip()
    if stripped.startswith("--"):
        return ""

    # اگر full-line `--` نبود، inline comment ها را حذف کن
    # فقط وقتی marker معتبر است که داخل string نباشد
    def cut_at_comment(s: str, markers=("--",)) -> str:
        in_string = False
        escape = False
        i = 0

        while i < len(s):
            ch = s[i]

            if in_string:
                if escape:
                    escape = False
                elif ch == '\\':
                    escape = True
                elif ch == '"':
                    in_string = False

                i += 1
                continue

            # خارج از string
            if ch == '"':
                in_string = True
                i += 1
                continue

            # بررسی markerها فقط بیرون از string
            for m in markers:
                if s.startswith(m, i):
                    return s[:i]

            i += 1

        return s

    return cut_at_comment(line).rstrip()


def _indent_level(line: str) -> int:
    # Counts leading spaces, assuming 2 spaces per indent level for strictness if needed
    # For now, just count spaces, as 'more indented' is the rule
    leading_spaces = len(line) - len(line.lstrip(' '))
    # If you want strict 2-space indents:
    # if leading_spaces % 2 != 0:
    #    raise TGLParseError("Indentation must be in multiples of 2 spaces", ???, line)
    return leading_spaces // 2 # Treat every 2 spaces as one level

def _parse_header(header_str: str) -> Tuple[str, Dict[str, Any]]:
    match = re.match(r'\[([^\]]+)\]\s*(?:\((.*)\))?', header_str)
    if not match:
        raise ValueError("Invalid header format")
    
    name = match.group(1).strip()
    attrs_str = match.group(2)
    attrs = {}
    if attrs_str:
        # Very basic attribute parsing, needs more robustness for complex values
        attr_pairs = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+?)(?:,|$)', attrs_str)
        for k, v_str in attr_pairs:
            try:
                attrs[k] = _parse_value(v_str.strip())
            except Exception:
                raise ValueError(f"Could not parse attribute value for '{k}'")
    return name, attrs

def _parse_identifier(ident_str: str) -> str:
    # Basic identifier validation
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', ident_str):
        raise ValueError(f"Invalid identifier: {ident_str}")
    return ident_str

def _split_top_level(s: str, delimiter: str = ',') -> list[str]:
    parts = []
    current = []

    in_quote = False
    quote_char = None
    escape = False
    square = 0
    curly = 0

    for ch in s:
        if escape:
            current.append(ch)
            escape = False
            continue

        if ch == '\\':
            current.append(ch)
            escape = True
            continue

        if ch in ('"', "'"):
            current.append(ch)
            if not in_quote:
                in_quote = True
                quote_char = ch
            elif quote_char == ch:
                in_quote = False
                quote_char = None
            continue

        if not in_quote:
            if ch == '[':
                square += 1
            elif ch == ']':
                square -= 1
            elif ch == '{':
                curly += 1
            elif ch == '}':
                curly -= 1
            elif ch == delimiter and square == 0 and curly == 0:
                parts.append(''.join(current).strip())
                current = []
                continue

        current.append(ch)

    if current:
        parts.append(''.join(current).strip())

    return parts

def _parse_value(value_str: str) -> Any:
    value_str = value_str.strip()

    # Try parsing as boolean
    if value_str.lower() == 'true':
        return True
    if value_str.lower() == 'false':
        return False

    # Try parsing as number (int or float)
    try:
        return int(value_str)
    except ValueError:
        pass

    try:
        return float(value_str)
    except ValueError:
        pass

    # Try parsing as list
    if value_str.startswith('[') and value_str.endswith(']'):
        list_content = value_str[1:-1].strip()
        if not list_content:
            return []

        try:
            elements = _split_top_level(list_content, ',')
            return [_parse_value(elem) for elem in elements if elem]
        except Exception:
            raise ValueError(f"Could not parse list: {value_str}")

    # Try parsing as dict
    if value_str.startswith('{') and value_str.endswith('}'):
        dict_content = value_str[1:-1].strip()
        if not dict_content:
            return {}

        try:
            result = {}
            entries = _split_top_level(dict_content, ',')

            for entry in entries:
                pair = _split_top_level(entry, ':')
                if len(pair) != 2:
                    raise ValueError(f"Invalid dict entry: {entry}")

                raw_key, raw_value = pair
                key = _parse_value(raw_key)
                value = _parse_value(raw_value)

                result[key] = value

            return result

        except Exception:
            raise ValueError(f"Could not parse dict: {value_str}")

    # Assume string if quoted
    if (value_str.startswith('"') and value_str.endswith('"')) or \
       (value_str.startswith("'") and value_str.endswith("'")):
        return value_str[1:-1]

    # fallback
    return value_str


# --- Main Parser ---
def load(text: str) -> TGLNode:
    lines = text.splitlines()
    # stack: (indent_level_in_2spaces, node)
    stack: List[Tuple[int, TGLNode]] = []
    root: Optional[TGLNode] = None

    # 1. delete of block comments
    text_no_blocks = remove_block_comments(text)

    # 2. normalize multiline values (NEW)
    text_no_blocks = normalize_multiline_values(text_no_blocks)

    lines = text_no_blocks.splitlines()
    cleaned_lines = []

    for line in lines:
        # 2. delete of line comments
        no_comment = _strip_comment(line)
        if not no_comment.strip():
            continue
        cleaned_lines.append(no_comment)

    for i, raw_line_with_indent in enumerate(cleaned_lines, start=1):
        # Preserve original line with indentation for error messages
        original_raw = raw_line_with_indent 
        
        # Process line: remove comments, trailing whitespace
        clean_line = raw_line_with_indent.rstrip()
        
        # Skip empty lines or lines that become empty after comment removal
        if not clean_line.strip():
            continue

        # Calculate indentation level based on leading spaces (each 2 spaces = 1 level)
        indent_level = _indent_level(raw_line_with_indent)
        stripped_line = clean_line.strip()

        # --- Logic for handling different line types ---

        # 1. Closing block (;)
        if stripped_line.startswith(";"):
            if stripped_line != ";":
                raise TGLParseError("Nothing allowed after ';'", i, original_raw)
            
            if not stack:
                raise TGLParseError("Unexpected ';' (no open block)", i, original_raw)

            # The indentation of ';' MUST match the indentation of the block header it closes.
            # Example: [world](indent=0) -> | [player](indent=0) -> ; (must be indent=0)
            #          [world](indent=0) -> | [player](indent=0) -> | name=... (indent=2) -> ; (must be indent=0)
            # This is the crucial part for structure.

            # expected_indent_level = stack[-1][0] # Indent level of the node we are about to pop
            
            # If current line's indentation is LESS than the stack top's indentation, it's an error
            # Because we are closing a block that is not the current innermost block.
            # We are also checking if the current indentation matches the block header's indentation.
            # This is because TGL implies structure: the ';' should align with the '[' that opened the block.

            # removed of this IF block
            # if indent_level != expected_indent_level:
            #      raise TGLParseError(
            #         f"';' indentation mismatch. Expected {expected_indent_level} (to match block header), got {indent_level}",
            #         i, original_raw
            #     )

            header_indent, _ = stack[-1]
            if indent_level < header_indent:
                 raise TGLParseError(
                    f"';' indentation error. Expected >= {header_indent}, got {indent_level}",
                    i, original_raw
                )

            stack.pop()
            continue

        # --- Processing lines that are NOT ';' ---
        
        # Check if we are inside a block (stack is not empty) for statements and child headers
        # If stack is empty, the ONLY valid line is a root block header '[...]'
        if not stack:
            # If stack is empty, we expect a root block header.
            if not stripped_line.startswith("["):
                raise TGLParseError("File must start with a block header like '[name]'", i, original_raw)
        else:
            # If stack is NOT empty, we are inside a block.
            # Any line here MUST be a statement ('| ...') or a child block header ('| [...]').
            # It cannot be a bare '[' header or something else.
            if not stripped_line.startswith("|"):
                raise TGLParseError("Inside blocks, lines must start with '|' (for statements/child blocks) or ';'", i, original_raw)

        # Now, handle the actual content based on whether it's a header or a statement
        
        # 2. Block Header ([...])
        if stripped_line.startswith("["):
            try:
                name, attrs = _parse_header(stripped_line)
            except Exception as e:
                raise TGLParseError(f"Invalid block header format: {e}", i, original_raw)

            new_node = TGLNode(name=name, attrs=attrs)

            if root is None:
                # This is the root block. It must be at indent level 0.
                if indent_level != 0:
                    raise TGLParseError("Root block must be at indentation level 0", i, original_raw)
                root = new_node
                stack.append((indent_level, root))
            else:
                # This is a child block header. It MUST follow a '|'.
                # The current code structure implies we are inside a block (stack is not empty).
                parent_indent_level, parent_node = stack[-1]

                # Rule: Child block must be strictly MORE indented than its parent's header.
                # Example: [world](indent=0) -> | [player](indent=0) -> This is allowed.
                #          [world](indent=0) -> | [player](indent=0) -> | name=... (indent=2) -> Then child block must be > indent 0.
                # We are checking indent_level of the child header against the PARENT's indent level.
                # If current node is '| [child]' at indent 0, and parent is '[world]' at indent 0: indent_level (0) is NOT > parent_indent_level (0).
                # So we need to adjust the rule: '| [child]' at same indent as parent is allowed.
                # But children of that child must be MORE indented.

                # Correct rule for child block header introduced by '|' or as next item after parent:
                # The child's indent level must be >= parent's indent level.
                # If it's the SAME level, it's treated as a sibling introduced by '|'.
                # If it's MORE indented, it's a nested child block.
                
                # Let's refine this: TGL syntax implies '| [child]' introduces a child.
                # If the current line starts with '[' AND we are inside a block (stack not empty),
                # it implies it's a child header introduced implicitly.
                # The previous line MUST have been '|' or ';'.
                # If previous line was '|', then indent_level of '[' can be same as parent.
                # If previous line was ';', then indent_level of '[' must be '> parent_indent_level'.

                # For simplicity and robustness for now:
                # A child block header '[' must have an indent level >= parent's indent level.
                # If it's STRICTLY GREATER, it's a nested child.
                # If it's EQUAL, it means it's a sibling introduced by '|' (which we haven't parsed yet in this branch)
                # This part needs careful handling based on whether '|' was present.
                
                # REVISED LOGIC: This branch ONLY handles bare '[' headers.
                # Bare '[' headers must be strictly MORE indented than parent.
                # The '| [child]' case is handled under statements.
                if indent_level <= parent_indent_level:
                     raise TGLParseError(f"Child block header '[' must be strictly more indented than parent (expected > {parent_indent_level}, got {indent_level})", i, original_raw)

                parent_node.children.append(new_node)
                stack.append((indent_level, new_node))
            continue

        # 3. Statement or Inline Child Block Header (| key = value OR | [child])
        if stripped_line.startswith("|"):
            if not stack:
                raise TGLParseError("Statement or inline child block header '|' found outside of any block", i, original_raw)
            
            payload = stripped_line[1:].strip() # Content after '|'
            parent_indent_level, parent_node = stack[-1]

            # Rule: Statements must be AT LEAST as indented as the current block header.
            # In your TGL, '| key = value' and '| [child]' can be at the same indent as the parent header.
            # So, we allow indent_level >= parent_indent_level.
            if indent_level < parent_indent_level:
                 raise TGLParseError(f"Statement/Child Header '|' indentation mismatch. Expected >= {parent_indent_level}, got {indent_level}", i, original_raw)

            # Inline Child Block Header: | [child](attrs)
            if payload.startswith("["):
                try:
                    cname, cattrs = _parse_header(payload)
                except Exception as e:
                    raise TGLParseError(f"Invalid inline child block header after '|': {e}", i, original_raw)
                
                child_node = TGLNode(name=cname, attrs=cattrs)
                parent_node.children.append(child_node)
                # The child node itself starts at the current indent level (same as parent for '| [child]')
                # Its body (if any) will be further indented.
                stack.append((indent_level, child_node))
                continue

            # Variable assignment: | key = value
            if "=" not in payload:
                raise TGLParseError("Invalid statement format. Expected '| key = value' or '| [child]'", i, original_raw)

            k, v = payload.split("=", 1)
            try:
                key = _parse_identifier(k.strip())
            except Exception as e:
                raise TGLParseError(f"Invalid variable name '{k.strip()}': {e}", i, original_raw)

            try:
                value = _parse_value(v.strip())
            except Exception as e:
                raise TGLParseError(f"Invalid value '{v.strip()}': {e}", i, original_raw)

            # Check if variable name conflicts with existing child names or block name
            # (This is a semantic check, could be optional)
            # if key in parent_node.children or key == parent_node.name:
            #    raise TGLParseError(f"Variable name '{key}' conflicts with existing node name or child", i, original_raw)
            
            parent_node.vars[key] = value
            continue
            
        # If we reach here, the line did not start with ';', '[', or '|' and was not empty/commented.
        # This is an unexpected format.
        raise TGLParseError("Syntax error. Lines must start with '[', '|', or ';'", i, original_raw)

    # --- Final Checks ---
    if root is None:
        raise TGLParseError("Empty file. A root block '[name]' is required.", 1, "")

    if stack:
        # If stack is not empty, it means some blocks were opened but not closed.
        open_nodes_info = " > ".join([f"'{n.name}' (indent={ind})" for ind, n in stack])
        raise TGLParseError(f"Unclosed block(s). Missing ';' for: {open_nodes_info}", len(lines) + 1, "")

    return root

# --- Helper functions for _parse_value to handle lists and quotes ---
# (These would need to be more robust for a production parser)

# Example Usage (assuming sample TGL is defined)
# test = r"""
# [world]
# | region = "forest"
# | [player](id=1001, active=true)
#   | name = "keyhan"
#   | hp = 95
#   | items = ["sword", "shield", 12, 12.5, true]
#   | [social]
#     | friends = ["ali", "mmd"]
#     | username = "key-112"
#     | age = 12
#     ;
#   ;
# | npcs = ["guard", "merchant"]
# ;
# """

# try:
#     ast = parse_tgl(test)
#     import json
#     print(json.dumps(ast.to_dict(), indent=4))
# except TGLParseError as e:
#     print(f"Parsing Error: {e}")
