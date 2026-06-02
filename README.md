# TGL (Tree Grammar Language)

TGL is a lightweight configuration language designed for hierarchical and tree-structured data.

It aims to keep nested configuration readable, explicit, and easy to parse.

## Table of Contents

* [Overview](#overview)
* [Why TGL?](#why-tgl)
* [Example](#example)
  * [JSON vs TGL](#json-vs-tgl)
* [Syntax Basics](#syntax-basics)
  * [Data Types](#data-types)
  * [Attributes](#attributes)
  * [Comments](#comments)
  * [Design Goals](#design-goals)
* [Planned Features](#planned-features)
* [Status](#status)

## Overview

TGL is built for data that naturally forms a tree: game configs, scene definitions, NPC data, UI layouts, dialogue trees, and other nested structures.

Unlike formats that depend heavily on indentation or verbose delimiters, TGL uses explicit node and field markers to keep structure readable and unambiguous.

## Why TGL?

Many existing formats solve general serialization, but they are not optimized for tree-first configuration.

* JSON is reliable, but deeply nested data becomes visually noisy.
* YAML is readable, but indentation mistakes can break structure.
* TOML is clean, but less comfortable for heavy tree nesting.
* XML is expressive, but too verbose for everyday config files.

TGL focuses on one thing: clear tree data representation.

## Example

### JSON

```json
{
  "world": {
    "region": "forest",
    "player": [
      {
        "id": 1001,
        "active": true,
        "name": "keyhan",
        "hp": 95,
        "items": ["sword", "shield", 12, 12.5, true],
        "social": {
          "friends": ["ali12345", "mmd"],
          "username": "key-112",
          "age": 12
        }
      }
    ],
    "npcs": ["guard", "merchant"]
  }
}
```

### TGL

```tgl
<-- this datas of my game -->

[world]
| region = "forest"

| [player](id=1001, active=true)
  | name = "keyhan"
  | hp = 95
  | items = ["sword", "shield", 12, 12.5, true]
  | [social]
    | friends = ["ali12345", "mmd"]
    | username = "key-112"
    | age = 12
    ;
  ;

| [player](id=1002, active=false) -- not online
  | name = "GPT-5"
  | hp = 100
  | items = ["rifle", 60, 24.78, false]
  | [social]
    | friends = ["key-112", "EER | Not connecting network"]
    | username = "ali12345"
    | age = 16
    ;
  ;

| [player](id=1003, active=true)
  | name = "parsa"
  | hp = 36
  | items = ["bow", "arrows", 1]
  | [social]
    | friends = []
    | username = "parsaalizade"
    | age = 8
    ;
  ;

| npcs = ["guard", "merchant"]
;
```

## JSON vs TGL

| JSON                                     | TGL                                              |
| ---------------------------------------- | ------------------------------------------------ |
| Standard and widely supported            | Designed specifically for tree data              |
| Uses braces and quotes for structure     | Uses explicit node markers and tree blocks       |
| Becomes harder to scan with deep nesting | Keeps parent-child relationships visible         |
| Great for general serialization          | Better fit for config-style hierarchical content |
| No built-in “tree intent”                | Tree structure is the core design goal           |

## Syntax Basics

### Root block

Every file starts with a root tree block.

```tgl
[world]
;
```

### Child or variable on a block

A child or variable must be written on a line that starts with `|`.

```tgl
[world]
| region = "forest"
;
```

### Nested child block

```tgl
[world]
| [player]
  | name = "keyhan"
  ;
;
```

### Attributes

```tgl
[player](id=1001, active=true)
```

## Data Types

TGL currently supports:

```tgl
| name = "keyhan"
| age = 12
| score = 12.5
| online = true
| items = ["sword", "shield", 12, 12.5, true]
```

Supported value types:

* String
* Integer
* Float
* Boolean
* Array

## Attributes

Attributes attach metadata to a node without turning them into normal fields.

```tgl
[player](id=1001, active=true)
```

This is useful for IDs, flags, tags, and other node-level metadata.

## Comments

Single-line comment:

```tgl
-- this is a comment
```

Block comment:

```tgl
<--
this is a
multi-line comment
-->
```

## Design Goals

TGL is built with these goals in mind:

1. Keep tree structure obvious
2. Make configuration files easy to scan
3. Reduce ambiguity in nested data
4. Stay simple to parse
5. Fit game data and similar hierarchical use cases

## Planned Features

* Null values
* Schema validation
* Syntax highlighting
* Formatter
* CLI tools
* Language Server Protocol support

## Status

TGL is currently under development, and the syntax may still evolve before the first stable release.

Feedback and ideas are welcome.
