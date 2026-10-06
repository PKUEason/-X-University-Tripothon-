# Libpedia · architectural sample 01

This is an authored Blender asset, loaded into the existing Three.js campus. The live preview is available via **图书馆样板** in the bottom view switcher. It provides exterior/front/side/interior camera presets, drag rotation and day/night lighting. **走进图书馆** resumes normal navigation from the student's existing position.

## Deliverables

- `libpedia.blend`: editable scene with named parts, edge bevel modifiers, fonts and curve-based structural members.
- `build_library.py`: deterministic Blender 4.5 authoring/export script. No paid generation service, downloaded third-party mesh or external texture dependency.
- `../../public/assets/library-refined.glb`: merged web asset (17 material meshes). Size/triangle count are recorded in `asset-report.json`.
- `../../src/library-asset.js`: runtime installation, transparent glazing, local reading lights, and atomic fallback replacement.

The scene contains a glazed reading pavilion, deep entrance canopy, metal frames and column feet, individually modeled books and furniture, a tapered multi-storey tower with annular floors and a helical stair, and a seamed titanium crown. Short-range ambient occlusion is baked into GLB vertex colors during export. The editable source is saved before export batching and shading bake; rerun the script to reproduce the GLB.

## Rebuild

From `campus-frontend`, with Blender 4.5 installed:

```sh
blender --background --python art/library/build_library.py
npm test
npm run build
```

The local proof run used the official Blender 4.5.9 ARM64 distribution, stored under ignored `.local/tools/Blender.app`. Team members can use their own Blender executable. The web runtime does not require Blender.

## Coordinates and limits

- Model local origin: centre of the pavilion; glTF Y-up, metres.
- Campus placement: `(0, 0, -25)`.
- Pavilion: 20 × 26 m. Clear central entry is aligned with the existing Library route and collision bounds. Navigation remains at ground level.
- Upper floors and spiral stair are visual architecture, **not navigable floors**. The first-floor reading hall is the walkable area.
- Glazing uses alpha transparency and environment reflections for frame-rate consistency; it is not path-traced refraction. Reading lights do not cast extra dynamic shadows.
- Other campus buildings and the student remain the previous assets. This is a single-building comparison sample, not a claim that the entire campus matches the reference render.
- If loading fails, the previous Library shell stays visible, and the inspection panel explicitly reports the fallback. It does not claim that the new asset loaded.

## Validation

The model test parses the actual GLB, checks dimensions, finite geometry, transparent materials and baked shading, then raycasts the central entrance at eye and shoulder heights. Runtime tests cover successful/failing asset replacement and preserving the student's position while changing inspection presets. Existing navigation tests still cover the Library route and other destinations.
