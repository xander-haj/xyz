"""Machine-readable clean-room audit for ZScream overworld parity domains."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainAudit:
    """One ZScream table family and its local clean-room owners."""

    key: str
    zscream_refs: tuple[str, ...]
    source_truth: tuple[str, ...]
    dump_owners: tuple[str, ...]
    patch_owners: tuple[str, ...]
    compile_owners: tuple[str, ...]
    runtime_owners: tuple[str, ...]
    editor_owners: tuple[str, ...]
    operation_kinds: tuple[str, ...]
    guardrails: tuple[str, ...]
    classification: str = "editable-clean-house-equivalent"
    completion: str = "codex-complete-pending-xander-execution"
    verification: tuple[str, ...] = ("read-only source audit",)
    intentional_differences: tuple[str, ...] = ()
    unsupported_or_out_of_scope: tuple[str, ...] = ()


PIPELINE_OWNERS = (
    "assets/extract_resources.py",
    "assets/restool.py",
    "assets/modtool.py",
    "assets/modding/schema.py",
    "assets/modding/overworld_builder.py",
    "dev_tools/overworld_editor/server.py",
)


AUDIT_DOMAINS: tuple[DomainAudit, ...] = (
    DomainAudit(
        key="map-properties",
        zscream_refs=(
            "ZeldaFullEditor/Data/Misc/OverworldMap.cs",
            "ZeldaFullEditor/NetZS.cs",
        ),
        source_truth=(
            "assets/overworld/overworld-*.yaml Header",
            "assets/overworld_dump/tables/area_metadata.json",
        ),
        dump_owners=("assets/dump_overworld.py", "assets/dump_overworld_metadata.py"),
        patch_owners=("assets/modding/yaml_patch.py", "dev_tools/overworld_editor/js/header-mod-export.js"),
        compile_owners=("assets/compile_resources.py",),
        runtime_owners=("src/overworld.c", "src/load_gfx.c"),
        editor_owners=("dev_tools/overworld_editor/js/header-controls.js",),
        operation_kinds=("metadata.header",),
        guardrails=("Header.palette only compiler-backed below 128", "special screens use kSpExit/source profiles"),
        intentional_differences=("special visual fields are not faked as normal Header.gfx/Header.palette",),
    ),
    DomainAudit(
        key="area-topology-and-size",
        zscream_refs=("ZeldaFullEditor/Data/Overworld.cs", "ZeldaFullEditor/NetZS.cs"),
        source_truth=("assets/overworld/overworld-*.yaml Header.size",),
        dump_owners=("assets/dump_overworld.py",),
        patch_owners=("assets/modding/topology_patch.py", "assets/modding/yaml_patch.py"),
        compile_owners=("assets/compile_resources.py",),
        runtime_owners=("src/overworld.c", "src/sprite.c"),
        editor_owners=(
            "dev_tools/overworld_viewer/js/map-groups.js",
            "dev_tools/overworld_editor/js/header-controls.js",
        ),
        operation_kinds=("metadata.header",),
        guardrails=(
            "size edits require parent/topology regeneration",
            "sprite/item ranges follow generated area heads",
        ),
        intentional_differences=("wide/tall are clean-house topology states generated with parent ids",),
    ),
    DomainAudit(
        key="static-overlays",
        zscream_refs=(
            "ZeldaFullEditor/Gui/Scene/SceneModes/OWOverlayMode.cs",
            "ZeldaFullEditor/Data/Overworld/OverlayData.cs",
            "ZeldaFullEditor/Data/Overworld/Overworld.cs",
            "ZeldaFullEditor/Save.cs SaveMapOverlays",
        ),
        source_truth=("assets/overworld/overworld-*.yaml Overlays",),
        dump_owners=("assets/dump_overworld.py", "assets/overworld_static_overlays.py"),
        patch_owners=("assets/modding/yaml_patch.py", "dev_tools/overworld_editor/js/static-overlay-mod-export.js"),
        compile_owners=("assets/compile_resources.py",),
        runtime_owners=("src/overworld.c",),
        editor_owners=("dev_tools/overworld_editor/js/static-overlay-controls.js",),
        operation_kinds=("metadata.static-overlay",),
        guardrails=(
            "static overlays are separate edit streams, not terrain copy",
            "Overlays patch paths must validate like the Python YAML patcher",
        ),
        intentional_differences=("local compiler emits metadata rows, not ZScream ASM tile-write streams",),
    ),
    DomainAudit(
        key="navigation-and-special-exits",
        zscream_refs=(
            "ZeldaFullEditor/Data/Overworld.cs",
            "ZeldaFullEditor/Gui/Scene/SceneModes/OWEntranceMode.cs",
            "ZeldaFullEditor/Gui/Scene/SceneModes/OWExitMode.cs",
            "ZeldaFullEditor/Save.cs SaveOWEntrances/SaveOWExits/SaveOWTransports",
        ),
        source_truth=("assets/overworld/overworld-*.yaml Travel/Entrances/Holes/Exits",),
        dump_owners=("assets/dump_overworld_metadata.py", "assets/dump_overworld.py"),
        patch_owners=("assets/modding/navigation_patch.py", "assets/modding/yaml_patch.py"),
        compile_owners=("assets/compile_resources.py",),
        runtime_owners=("src/overworld.c",),
        editor_owners=(
            "dev_tools/overworld_editor/js/navigation-mod-export.js",
            "dev_tools/overworld_editor/js/navigation-allocation-model.js",
            "dev_tools/overworld_editor/js/navigation-record-controls.js",
        ),
        operation_kinds=(
            "metadata.travel",
            "metadata.entrance",
            "metadata.hole",
            "metadata.exit",
        ),
        guardrails=(
            "fixed global slots stay unique",
            "navigation patch import must reject sparse or missing nested rows",
            "special exits must own rooms 0x180..0x18f",
        ),
        intentional_differences=(
            "deleted entrances/holes/exits are fixed-slot sentinels",
            "travel delete remains unsupported because traced transports are live fixed rows",
        ),
    ),
    DomainAudit(
        key="special-map-property-tables",
        zscream_refs=(
            "ZeldaFullEditor/Data/OverworldMap.cs",
            "ZeldaFullEditor/Data/Misc/OverworldMap.cs",
            "ZeldaFullEditor/Save.cs SaveMapProperties",
        ),
        source_truth=("src/overworld.c kSpExit_*", "assets/overworld_dump/tables/area_metadata.json"),
        dump_owners=("assets/dump_overworld.py",),
        patch_owners=("assets/modding/navigation_patch.py",),
        compile_owners=("assets/compile_resources.py",),
        runtime_owners=("src/overworld.c", "src/load_gfx.c"),
        editor_owners=("dev_tools/overworld_editor/js/special-visual-controls.js",),
        operation_kinds=("metadata.exit",),
        guardrails=("edit kSpExit-backed payloads, not fake Header.gfx/Header.palette",),
        intentional_differences=(
            "local kSpExit payloads replace ZScream expanded temp ASM tables",
            "custom tile GFX and subscreen overlay ASM tables are separate preview/read-only domains",
        ),
    ),
    DomainAudit(
        key="hidden-items",
        zscream_refs=("ZeldaFullEditor/Data/Types/SecretItemType.cs", "ZeldaFullEditor/Data/Overworld.cs"),
        source_truth=("assets/overworld/overworld-*.yaml Items", "src/sprite.c Sprite_SpawnSecret tables"),
        dump_owners=("assets/dump_overworld_interactions.py", "assets/dump_overworld.py"),
        patch_owners=("assets/modding/yaml_patch.py",),
        compile_owners=("assets/compile_resources.py",),
        runtime_owners=("src/sprite.c", "src/overworld.c"),
        editor_owners=(
            "dev_tools/overworld_editor/js/interaction-mod-export.js",
            "dev_tools/overworld_editor/js/secret-item-shape.js",
        ),
        operation_kinds=("metadata.item",),
        guardrails=("secret codes are not the same namespace as live sprite ids",),
        intentional_differences=("bombable redraw persistence is derived from edited kOverworldSecrets",),
    ),
    DomainAudit(
        key="overworld-sprites",
        zscream_refs=("ZeldaFullEditor/Data/Overworld.cs", "ZeldaFullEditor/Data/Types/SpriteDraw.cs"),
        source_truth=("assets/overworld/overworld-*.yaml Sprites*", "src/sprite_main.c draw routines"),
        dump_owners=("assets/dump_overworld_sprites.py", "assets/dump_overworld_sprite_oam.py"),
        patch_owners=("assets/modding/yaml_patch.py",),
        compile_owners=("assets/compile_resources.py",),
        runtime_owners=("src/sprite.c", "src/sprite_main.c"),
        editor_owners=(
            "dev_tools/overworld_editor/js/sprite-mod-export.js",
            "dev_tools/overworld_editor/js/enemy-source-oam.js",
            "dev_tools/overworld_editor/js/enemy-source-oam-recipes.js",
            "dev_tools/overworld_editor/js/enemy-oam-classification.js",
        ),
        operation_kinds=("metadata.sprite",),
        guardrails=(
            "do not sort placement lists",
            "cross-world copy keeps per-placement custom visual sidecars",
            "renderer coverage changes must remain presentation-only",
        ),
        intentional_differences=("custom visual sidecar is local metadata after the vanilla sprite sentinel",),
    ),
    DomainAudit(
        key="palette-tables",
        zscream_refs=("ZeldaFullEditor/Data/Misc/OverworldMap.cs", "ZeldaFullEditor/GFX.cs"),
        source_truth=("assets/overworld_dump/palettes/*.json", "generated kOverworldBgPalettes"),
        dump_owners=("assets/dump_overworld_palettes.py", "assets/dump_overworld.py"),
        patch_owners=("assets/modding/palette_patch.py",),
        compile_owners=("assets/compile_resources.py",),
        runtime_owners=("src/load_gfx.c", "src/overworld.c"),
        editor_owners=("dev_tools/overworld_editor/js/panels.js",),
        operation_kinds=("palette.color-edit", "palette.assignment"),
        guardrails=("generated 160-entry bg palette table must not read local $04C635",),
        intentional_differences=(
            "raw palette patch JSON owns palette.* operations",
            "normal Header palette owns 0x00..0x7f; special BG palettes use kSpExit_PalBg",
        ),
    ),
    DomainAudit(
        key="tile-types-and-terrain",
        zscream_refs=("ZeldaFullEditor/Data/Overworld.cs", "ZeldaFullEditor/NetZS.cs"),
        source_truth=("assets/overworld_maps/*.json", "assets/overworld_dump/tables/tile_tables.json"),
        dump_owners=("assets/dump_overworld.py", "assets/dump_overworld_tile_attributes.py"),
        patch_owners=("assets/modding/terrain_patch.py", "assets/modding/tile_patch.py"),
        compile_owners=("assets/compile_resources.py",),
        runtime_owners=("src/overworld.c", "src/tile_detect.c"),
        editor_owners=(
            "dev_tools/overworld_editor/js/mod-export.js",
            "dev_tools/overworld_editor/js/map32-transforms.js",
        ),
        operation_kinds=(
            "terrain.map32-placement",
            "tile.map32-definition",
            "tile.map16-definition",
            "tile.map8-word",
            "tile.map8-attribute",
        ),
        guardrails=("terrain copy workflow remains unchanged", "tile word bits preserve SNES BG semantics"),
    ),
    DomainAudit(
        key="graphics-recipes",
        zscream_refs=("ZeldaFullEditor/GfxGroups.cs",),
        source_truth=("assets/overworld_dump/gfx",),
        dump_owners=("assets/dump_overworld_sprites.py", "assets/dump_overworld.py"),
        patch_owners=("assets/modding/chr_patch.py",),
        compile_owners=("assets/compile_resources.py",),
        runtime_owners=("src/load_gfx.c",),
        editor_owners=("dev_tools/overworld_editor/js/panels.js",),
        operation_kinds=("chr.tile-recipe",),
        guardrails=("graphics edits are raw patch recipes, not copied ZScream draw data",),
    ),
    DomainAudit(
        key="gravestones",
        zscream_refs=("ZeldaFullEditor/NetZS.cs",),
        source_truth=("src/overworld_gravestones.c",),
        dump_owners=("assets/dump_overworld_gravestones.py",),
        patch_owners=("assets/modding/gravestone_patch.py",),
        compile_owners=("assets/compile_resources.py",),
        runtime_owners=("src/overworld.c", "src/overworld_gravestones.c"),
        editor_owners=("dev_tools/overworld_editor/js/gravestone-mod-export.js",),
        operation_kinds=("gravestone.record",),
        guardrails=("gravestone tilemap must match x/y/area",),
    ),
    DomainAudit(
        key="dialogue-text",
        zscream_refs=("ZeldaFullEditor/NetZS.cs",),
        source_truth=("assets/dialogue.txt", "src/messaging.c"),
        dump_owners=("assets/editor_asset_dialogue.py", "assets/editor_asset_npc_dialogue.py"),
        patch_owners=(
            "assets/modding/dialogue_patch.py",
            "dev_tools/overworld_editor/js/dialogue-mod-export.js",
        ),
        compile_owners=("assets/compile_resources.py",),
        runtime_owners=("src/messaging.c",),
        editor_owners=("dev_tools/overworld_editor/js/dialogue-controls.js",),
        operation_kinds=("dialogue.text",),
        guardrails=(
            "text edits replace dialogue.txt lines only",
            "literal newlines are rejected because dialogue.txt is one source row per id",
            "sprite handlers still own which message ids are shown",
        ),
    ),
    DomainAudit(
        key="secondary-overlays-and-subscreen-fx",
        zscream_refs=(
            "ZeldaFullEditor/Data/Overworld/Overworld.cs",
            "ZeldaFullEditor/Data/Overworld/OverlayData.cs",
        ),
        source_truth=("assets/overworld_dump/tables/overlay_metadata.json", "src/overworld.c overlay loaders"),
        dump_owners=("assets/dump_overworld.py",),
        patch_owners=(),
        compile_owners=(),
        runtime_owners=("src/overworld.c", "src/nmi.c"),
        editor_owners=(
            "dev_tools/overworld_viewer/js/renderer.js",
            "dev_tools/overworld_editor/js/layer-state.js",
        ),
        operation_kinds=(),
        guardrails=("secondary/subscreen overlays are preview/read-only in this parity pass",),
        classification="read-only-preview",
        completion="codex-audited-read-only",
        intentional_differences=("static overlay editing is separate from secondary/subscreen overlay preview",),
        unsupported_or_out_of_scope=("editing secondary overlay streams", "editing subscreen effect tables"),
    ),
    DomainAudit(
        key="bomb-doors-and-persisted-redraw",
        zscream_refs=("ZeldaFullEditor/Data/Overworld/Overworld.cs", "ZeldaFullEditor/NetZS.cs"),
        source_truth=(
            "assets/overworld/overworld-*.yaml Items code 0x86",
            "assets/overworld/overworld-*.yaml Exits[].door",
        ),
        dump_owners=("assets/dump_overworld_interactions.py", "assets/dump_overworld_metadata.py"),
        patch_owners=(
            "assets/modding/yaml_patch.py",
            "assets/modding/navigation_patch.py",
            "dev_tools/overworld_editor/js/interaction-mod-export.js",
            "dev_tools/overworld_editor/js/navigation-mod-export.js",
        ),
        compile_owners=("assets/compile_resources.py",),
        runtime_owners=("src/overworld.c", "src/sprite.c"),
        editor_owners=(
            "dev_tools/overworld_editor/js/secret-item-controls.js",
            "dev_tools/overworld_editor/js/exit-door-controls.js",
        ),
        operation_kinds=("metadata.item", "metadata.exit"),
        guardrails=("bombable redraw follows edited kOverworldSecrets", "exit door payloads stay validated"),
        intentional_differences=("runtime scans compiled secrets instead of a hardcoded bomb-door redraw table",),
    ),
)


def known_zscream_patch_kinds() -> set[str]:
    """Return every patch operation kind covered by the parity audit."""
    return {kind for domain in AUDIT_DOMAINS for kind in domain.operation_kinds}


def assert_zscream_parity_contract() -> None:
    """Validate the audit metadata itself before accepting patch documents."""
    if not PIPELINE_OWNERS:
        raise ValueError("Incomplete ZScream parity shared pipeline owners.")
    for domain in AUDIT_DOMAINS:
        required = (domain.zscream_refs, domain.source_truth, domain.dump_owners, domain.editor_owners,
                    domain.guardrails, domain.classification, domain.completion)
        if any(not value for value in required):
            raise ValueError("Incomplete ZScream parity audit domain %s." % domain.key)
        if domain.classification.startswith("editable") and not domain.operation_kinds:
            raise ValueError("Editable ZScream parity domain %s has no patch kinds." % domain.key)
        if domain.classification.startswith("editable") and not domain.patch_owners:
            raise ValueError("Editable ZScream parity domain %s has no patch owner." % domain.key)
        if domain.classification.startswith("editable") and not domain.compile_owners:
            raise ValueError("Editable ZScream parity domain %s has no compiler owner." % domain.key)
        if domain.classification.startswith("editable") and not domain.runtime_owners:
            raise ValueError("Editable ZScream parity domain %s has no runtime owner." % domain.key)


def zscream_audit_rows() -> list[dict]:
    """Return JSON-friendly audit rows for tools that need to report coverage."""
    return [
        {
            "key": domain.key,
            "zscreamRefs": list(domain.zscream_refs),
            "sourceTruth": list(domain.source_truth),
            "dumpOwners": list(domain.dump_owners),
            "patchOwners": list(domain.patch_owners),
            "compileOwners": list(domain.compile_owners),
            "runtimeOwners": list(domain.runtime_owners),
            "editorOwners": list(domain.editor_owners),
            "pipelineOwners": list(PIPELINE_OWNERS),
            "operationKinds": list(domain.operation_kinds),
            "guardrails": list(domain.guardrails),
            "classification": domain.classification,
            "completion": domain.completion,
            "verification": list(domain.verification),
            "intentionalDifferences": list(domain.intentional_differences),
            "unsupportedOrOutOfScope": list(domain.unsupported_or_out_of_scope),
        }
        for domain in AUDIT_DOMAINS
    ]
