from __future__ import annotations

import base64
from collections.abc import Callable
from io import BytesIO
from typing import Any

import streamlit as st
from PIL import Image

from layout_interaction import AREA_EVENT_KEYS, normalize_area_name


_INTERACTIVE_PREVIEW_HTML = """
<div id="tm-preview-root" tabindex="0" style="outline:none; position:relative; width:100%;">
  <img id="tm-preview-img" alt="Title preview" style="width:100%; height:auto; display:block; border-radius:4px;" />
  <svg id="tm-preview-svg" style="position:absolute; left:0; top:0; width:100%; height:100%; pointer-events:auto;"></svg>
</div>
"""

_INTERACTIVE_PREVIEW_CSS = """
#tm-preview-root:focus {
  box-shadow: 0 0 0 2px var(--st-primary-color, #ff4b4b);
}
.tm-guide {
  fill: rgba(255, 255, 255, 0.08);
  stroke: rgba(255, 255, 255, 0.75);
  stroke-width: 2;
  cursor: pointer;
}
.tm-guide.selected {
  fill: rgba(255, 210, 70, 0.18);
  stroke: rgba(255, 210, 70, 0.95);
  stroke-width: 3;
}
"""

_INTERACTIVE_PREVIEW_JS = """
export default function (component) {
  const { data, parentElement, setTriggerValue } = component
  const root = parentElement.querySelector("#tm-preview-root")
  const img = parentElement.querySelector("#tm-preview-img")
  const svg = parentElement.querySelector("#tm-preview-svg")
  if (!root || !img || !svg) return

  const designWidth = (data && data.design_width) || 1920
  const designHeight = (data && data.design_height) || 1080
  const boxes = (data && data.boxes) || {}
  const selected = (data && data.selected) || "title"
  const positionStep = (data && data.position_step) || 5
  const fontStep = (data && data.font_step) || 5
  const imageB64 = (data && data.image_b64) || ""

  if (imageB64) {
    const nextSrc = "data:image/png;base64," + imageB64
    if (img.getAttribute("src") !== nextSrc) {
      img.setAttribute("src", nextSrc)
    }
  }

  function displaySize() {
    const width = img.clientWidth || root.clientWidth || 1
    const height = img.clientHeight || Math.round(width * (designHeight / designWidth)) || 1
    return { width, height }
  }

  function toDisplayBox(box) {
    const { width, height } = displaySize()
    const sx = width / designWidth
    const sy = height / designHeight
    return {
      x: (box.x || 0) * sx,
      y: (box.y || 0) * sy,
      width: (box.width || 0) * sx,
      height: (box.height || 0) * sy,
    }
  }

  function drawGuides() {
    const { width, height } = displaySize()
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`)
    svg.setAttribute("width", String(width))
    svg.setAttribute("height", String(height))
    svg.innerHTML = ""
    const order = ["service", "speaker", "title"]
    for (const key of order) {
      const box = boxes[key]
      if (!box) continue
      const d = toDisplayBox(box)
      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect")
      rect.setAttribute("x", String(d.x))
      rect.setAttribute("y", String(d.y))
      rect.setAttribute("width", String(Math.max(1, d.width)))
      rect.setAttribute("height", String(Math.max(1, d.height)))
      rect.setAttribute("class", key === selected ? "tm-guide selected" : "tm-guide")
      rect.dataset.area = key
      rect.addEventListener("click", (evt) => {
        evt.preventDefault()
        evt.stopPropagation()
        root.focus()
        setTriggerValue("layout_event", {
          event: "select",
          area: key,
          nonce: Date.now(),
        })
      })
      rect.addEventListener("dblclick", (evt) => {
        evt.preventDefault()
        evt.stopPropagation()
        if (key !== "title") return
        setTriggerValue("layout_event", {
          event: "autofit",
          area: "title",
          nonce: Date.now(),
        })
      })
      svg.appendChild(rect)
    }
  }

  function onKeyDown(evt) {
    const key = evt.key
    let payload = null
    if (key === "ArrowUp") {
      payload = { event: "move", area: selected, dy: -positionStep, dx: 0 }
    } else if (key === "ArrowDown") {
      payload = { event: "move", area: selected, dy: positionStep, dx: 0 }
    } else if (key === "ArrowLeft") {
      payload = { event: "move", area: selected, dx: -positionStep, dy: 0 }
    } else if (key === "ArrowRight") {
      payload = { event: "move", area: selected, dx: positionStep, dy: 0 }
    } else if (key === "+" || key === "=") {
      payload = { event: "font", area: selected, font_delta: fontStep }
    } else if (key === "-" || key === "_") {
      payload = { event: "font", area: selected, font_delta: -fontStep }
    }
    if (!payload) return
    evt.preventDefault()
    payload.nonce = Date.now()
    setTriggerValue("layout_event", payload)
  }

  img.onload = () => drawGuides()
  window.addEventListener("resize", drawGuides)
  root.onkeydown = onKeyDown
  root.onclick = () => root.focus()

  // Initial draw after layout.
  requestAnimationFrame(() => {
    drawGuides()
    root.focus()
  })

  return () => {
    window.removeEventListener("resize", drawGuides)
    root.onkeydown = null
    root.onclick = null
  }
}
"""

_interactive_preview = st.components.v2.component(
    "titlemaker_interactive_preview",
    html=_INTERACTIVE_PREVIEW_HTML,
    css=_INTERACTIVE_PREVIEW_CSS,
    js=_INTERACTIVE_PREVIEW_JS,
)


def image_to_base64_png(image: Image.Image) -> str:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def render_interactive_preview(
    image: Image.Image,
    boxes: dict[str, dict[str, int]],
    selected_area: str,
    *,
    position_step: int = 5,
    font_step: int = 5,
    design_width: int = 1920,
    design_height: int = 1080,
    key: str = "interactive_preview",
    on_layout_event: Callable[[], None] | None = None,
) -> Any:
    """Mount the interactive preview and return the component result."""
    if on_layout_event is None:
        on_layout_event = lambda: None

    selected_key = AREA_EVENT_KEYS.get(normalize_area_name(selected_area), "title")
    return _interactive_preview(
        data={
            "image_b64": image_to_base64_png(image),
            "boxes": boxes,
            "selected": selected_key,
            "position_step": int(position_step),
            "font_step": int(font_step),
            "design_width": int(design_width),
            "design_height": int(design_height),
        },
        key=key,
        height="auto",
        on_layout_event_change=on_layout_event,
    )
