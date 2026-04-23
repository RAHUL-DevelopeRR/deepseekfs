"""
Neuron — Jinja2 Compatibility Patches
======================================
Registers custom Jinja2 extensions to handle model-specific template 
tags that aren't part of standard Jinja2.

SmolLM3's chat template uses {% generation %} / {% endgeneration %} 
to mark generation regions. Standard Jinja2 doesn't recognize these,
causing a TemplateSyntaxError during model loading in llama-cpp-python.

This module MUST be imported before llama_cpp to patch the Environment.
"""
from __future__ import annotations

from jinja2 import nodes
from jinja2.ext import Extension
import jinja2

_PATCHED = False


class GenerationTagExtension(Extension):
    """Handles {% generation %} / {% endgeneration %} as transparent blocks.
    
    These tags are used by SmolLM3 and similar models to delineate 
    the region where the model should generate text. We treat them
    as pass-through blocks that simply render their body content.
    """
    tags = {"generation"}

    def parse(self, parser):
        lineno = next(parser.stream).lineno
        body = parser.parse_statements(
            ["name:endgeneration"], drop_needle=True
        )
        return nodes.CallBlock(
            self.call_method("_passthrough"), [], [], body
        ).set_lineno(lineno)

    def _passthrough(self, caller):
        return caller()


def patch_jinja2():
    """Monkey-patch jinja2.Environment to include our custom extensions.
    
    Safe to call multiple times — only patches once.
    Must be called BEFORE importing llama_cpp.
    """
    global _PATCHED
    if _PATCHED:
        return
    
    _orig_init = jinja2.Environment.__init__

    def _patched_init(self, *args, **kwargs):
        extensions = list(kwargs.get("extensions", []))
        if GenerationTagExtension not in extensions:
            extensions.append(GenerationTagExtension)
        kwargs["extensions"] = extensions
        _orig_init(self, *args, **kwargs)

    jinja2.Environment.__init__ = _patched_init
    _PATCHED = True


# Auto-patch on import
patch_jinja2()
