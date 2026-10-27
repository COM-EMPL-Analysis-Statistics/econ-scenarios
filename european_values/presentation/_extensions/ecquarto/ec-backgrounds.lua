-- EC corporate slide styling, applied per output format so that QMD authors
-- only need:
--   ## Title              -> regular slide (emblem bottom-right)
--   ## Title {.section}   -> section divider (blue band on top, title below)
--   ## Title {.end}       -> end slide (mint background, CC BY logo, emblem)
--
-- reveal.js : slide looks are driven by data-background-* attributes + the SCSS theme.
--             Images are inlined as data URIs so the extension folder never has to be
--             referenced from the .qmd.
-- pptx      : slide looks come from the layouts in ec-corporate.pptx (reference-doc);
--             this filter picks the right layout, folds the section subtitle into the
--             title, and turns colour spans into native coloured text runs.

local is_pptx = quarto.doc.is_format("pptx")

local colors = {
  green  = '44BA7E',
  purple = '48038C',
  orange = 'FF712C',
  yellow = 'FFD34E',
  pink   = 'DD0C86',
  blue   = '003399',
}

-- Full path of a file shipped next to this filter (inside the extension folder).
local function asset(name)
  return quarto.utils.resolve_path(name)
end

local function data_uri(name)
  local f = assert(io.open(asset(name), 'rb'))
  local bytes = f:read('a')
  f:close()
  return 'data:image/png;base64,' .. quarto.base64.encode(bytes)
end

-- --------------------------------------------------------------------------
-- reveal.js (and anything that is not pptx)
-- --------------------------------------------------------------------------
local function reveal_document(doc)
  local emblem = data_uri('ec-emblem.png')

  -- title slide: blue background with the white EC logo bottom-right
  doc.meta['title-slide-attributes'] = pandoc.MetaMap({
    ['data-background-color']    = pandoc.MetaString('#003399'),
    ['data-background-image']    = pandoc.MetaString(data_uri('ec-logo-white.png')),
    ['data-background-size']     = pandoc.MetaString('280px auto'),
    ['data-background-position'] = pandoc.MetaString('calc(100% - 40px) calc(100% - 30px)'),
  })

  local out = pandoc.List()
  for _, b in ipairs(doc.blocks) do
    out:insert(b)
    if b.t == 'Header' and b.level == 2 then
      if b.classes:includes('section') then
        b.attributes['data-background-gradient'] =
          'linear-gradient(to bottom, #003399 0%, #003399 55%, #FFFFFF 55%, #FFFFFF 100%)'
      else
        if b.classes:includes('end') then
          b.attributes['data-background-color'] = '#C6E5DF'
          -- CC BY logo directly under the title
          out:insert(pandoc.Para({
            pandoc.Image({}, data_uri('cc-by-logo.png'), '', pandoc.Attr('', { 'cc-by-logo', 'nostretch' }))
          }))
        end
        b.attributes['data-background-image'] = emblem
        b.attributes['data-background-size'] = '160px auto'
        b.attributes['data-background-position'] = 'calc(100% - 35px) calc(100% - 25px)'
      end
    end
  end
  doc.blocks = out
  return doc
end

-- --------------------------------------------------------------------------
-- pptx helpers
-- --------------------------------------------------------------------------
local function xml_escape(s)
  return (s:gsub('&', '&amp;'):gsub('<', '&lt;'):gsub('>', '&gt;'))
end

-- Build a native DrawingML text run.
-- opts: { fill = 'RRGGBB', highlight = 'RRGGBB', bold = bool, italic = bool,
--         underline = bool, size = hundredths-of-pt, rid = 'rIdN' (hyperlink relationship) }
local function openxml_run(text, opts)
  opts = opts or {}
  local rpr = '<a:rPr lang="en-US" dirty="0"'
  if opts.bold then rpr = rpr .. ' b="1"' end
  if opts.italic then rpr = rpr .. ' i="1"' end
  if opts.underline then rpr = rpr .. ' u="sng"' end
  if opts.size then rpr = rpr .. ' sz="' .. opts.size .. '"' end
  rpr = rpr .. '>'
  if opts.fill then
    rpr = rpr .. '<a:solidFill><a:srgbClr val="' .. opts.fill .. '"/></a:solidFill>'
  end
  if opts.highlight then
    rpr = rpr .. '<a:highlight><a:srgbClr val="' .. opts.highlight .. '"/></a:highlight>'
  end
  if opts.rid then
    rpr = rpr .. '<a:hlinkClick r:id="' .. opts.rid .. '"/>'
  end
  rpr = rpr .. '</a:rPr>'
  return pandoc.RawInline('openxml', '<a:r>' .. rpr .. '<a:t>' .. xml_escape(text) .. '</a:t></a:r>')
end

-- Flatten inlines into coloured runs, keeping bold/italic.
local function inlines_to_runs(inlines, opts, out)
  for _, il in ipairs(inlines) do
    if il.t == 'Str' then
      out:insert(openxml_run(il.text, opts))
    elseif il.t == 'Space' or il.t == 'SoftBreak' then
      out:insert(openxml_run(' ', opts))
    elseif il.t == 'LineBreak' then
      out:insert(pandoc.LineBreak())
    elseif il.t == 'Link' then
      if opts.links then
        -- Styled hyperlink. A raw run can only point at a relationship id, and only
        -- Pandoc can create those. So an invisible (zero-width) Pandoc link registers
        -- the target; Pandoc numbers a slide's media/link relationships sequentially
        -- (rId2 = background image, then one per link in document order), and the
        -- visible styled run references that id.
        out:insert(pandoc.Link({ pandoc.Str('\u{200B}') }, il.target, il.title))
        local o = {}; for k, v in pairs(opts) do o[k] = v end
        o.links = nil; o.underline = true; o.rid = 'rId' .. opts.links.next
        opts.links.next = opts.links.next + 1
        inlines_to_runs(il.content, o, out)
      else
        out:insert(il)   -- keep Pandoc's own link run (default size)
      end
    elseif il.t == 'Strong' then
      local o = {}; for k, v in pairs(opts) do o[k] = v end; o.bold = true
      inlines_to_runs(il.content, o, out)
    elseif il.t == 'Emph' then
      local o = {}; for k, v in pairs(opts) do o[k] = v end; o.italic = true
      inlines_to_runs(il.content, o, out)
    elseif il.content then
      inlines_to_runs(il.content, opts, out)
    elseif il.text then
      out:insert(openxml_run(il.text, opts))
    end
  end
  return out
end

local function pptx_span(el)
  for name, hex in pairs(colors) do
    if el.classes:includes(name) then
      return inlines_to_runs(el.content, { fill = hex }, pandoc.List())
    elseif el.classes:includes('bg-' .. name) then
      local fg = (name == 'yellow') and colors.blue or 'FFFFFF'
      return inlines_to_runs(el.content, { fill = fg, highlight = hex }, pandoc.List())
    end
  end
  return nil
end

local function is_image_para(b)
  return b.t == 'Para' and #b.content == 1 and b.content[1].t == 'Image'
end

-- Author(s) on the title slide: blue italic text on a yellow highlight, as in the HTML theme.
local function pptx_author(meta)
  local function styled(v)
    local name = pandoc.utils.stringify(v)
    if name == '' then return nil end
    return pandoc.MetaInlines({ openxml_run('\u{A0}' .. name .. '\u{A0}', { fill = colors.blue, highlight = colors.yellow, italic = true }) })
  end
  local a = meta.author
  if a == nil then return end
  if pandoc.utils.type(a) == 'List' then
    local list = pandoc.List()
    for _, v in ipairs(a) do
      local s = styled(v)
      if s then
        -- local change: a blank line between authors
        if #list > 0 then list:insert(pandoc.MetaInlines({ pandoc.Str('\u{A0}') })) end
        list:insert(s)
      end
    end
    meta.author = pandoc.MetaList(list)
  else
    meta.author = styled(a)
  end
end

-- Restructure the document for pptx:
--  * {.section}: level-1 header -> "Section Header" layout; the first paragraph
--    after it becomes a smaller subtitle line inside the same title box.
--  * {.end}: mint background image (CC BY logo is part of it); title and text are
--    laid out in the body placeholder to mirror the HTML slide; image-only
--    paragraphs on that slide are dropped (Pandoc would put them on their own slide).
local function pptx_document(doc)
  pptx_author(doc.meta)
  local out = pandoc.List()
  local blocks = doc.blocks
  local i = 1
  while i <= #blocks do
    local b = blocks[i]
    if b.t == 'Header' and b.level == 2 and b.classes:includes('section') then
      local content = pandoc.List(b.content)
      local nxt = blocks[i + 1]
      if nxt and nxt.t == 'Para' then
        content:insert(pandoc.LineBreak())
        content:insert(openxml_run(pandoc.utils.stringify(nxt), { size = 2000 }))
        i = i + 1
      end
      out:insert(pandoc.Header(1, content, b.attr))
    elseif b.t == 'Header' and b.level == 2 and b.classes:includes('end') then
      -- The title placeholder sits at the top of the layout, but the HTML end slide
      -- has its big light title mid-slide with the CC BY logo under it. So the
      -- title placeholder is left blank and everything is laid out in the body:
      --   big blue "Thank you" / blank line where the logo (part of the background
      --   image) sits / the remaining text in blue.
      local hdr = pandoc.Header(2, { openxml_run('\u{A0}') }, b.attr)
      hdr.attributes['background-image'] = asset('ec-bg-end.png')
      out:insert(hdr)
      out:insert(pandoc.Para({ openxml_run(pandoc.utils.stringify(b.content), { fill = colors.blue, size = 4400 }) }))
      out:insert(pandoc.Para({ openxml_run('\u{A0}', { size = 4400 }) }))
      -- rId2 is the background image registered above; links on this slide get rId3, rId4, ...
      -- (verified with pandoc 3.6; relationship numbering has been stable since pandoc 2.x,
      -- but fall back to plain Pandoc links on a future major version rather than risk a
      -- broken file).
      local links = PANDOC_VERSION < pandoc.types.Version('4.0') and { next = 3 } or nil
      local j = i + 1
      while j <= #blocks and not (blocks[j].t == 'Header' and blocks[j].level <= 2) do
        local blk = blocks[j]
        if blk.t == 'Para' or blk.t == 'Plain' then
          out:insert(pandoc.Para(inlines_to_runs(blk.content, { fill = colors.blue, size = 1300, links = links }, pandoc.List())))
        elseif not is_image_para(blk) then
          out:insert(blk)
        end
        j = j + 1
      end
      i = j - 1
    else
      out:insert(b)
    end
    i = i + 1
  end
  doc.blocks = out
  return doc
end

-- --------------------------------------------------------------------------
-- Register filters by format
-- --------------------------------------------------------------------------
if is_pptx then
  return {
    { Span = pptx_span },
    { Pandoc = pptx_document },
  }
else
  return {
    { Pandoc = reveal_document },
  }
end
