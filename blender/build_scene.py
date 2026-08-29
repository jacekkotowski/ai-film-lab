"""
build_scene.py  --  the Blender backend. Runs INSIDE Blender.

    blender -b -P blender/build_scene.py -- --project projects/film_001

Honest description of what this buys you TODAY, and what it buys you LATER,
because the difference matters and I don't want to oversell it.

TODAY, on a flat photograph, Blender gives you:
  - a real camera with a real focal length and real sensor
  - Blender's texture filtering and AgX view transform
  - proper 3D motion blur
...and that is roughly it. On a FLAT plane, a dolly and a zoom are
mathematically identical, and depth of field does nothing, because there
is no depth. The OpenCV renderer produces near-identical results far faster.
This is why `uv run film final` does not use Blender by default.

LATER, once analysis/depth/<name>.png exists, the same script gives you
things the 2D path fundamentally cannot:
  - true parallax with real occlusion (near things pass far things)
  - rack focus THROUGH a photograph
  - dolly vs zoom actually diverging, which is the real cinematic tell
This script already reads depth maps if it finds them. That is the point
of writing it now: the scaffolding is in place, so adding depth later is
a model download, not a rewrite.

Output: PNG sequences in out/blender/<shot_id>/, which the CLI encodes.
NOTE: written carefully but not executable in my sandbox -- expect to
send me the first traceback.
"""

import argparse
import math
import sys
from pathlib import Path

import bpy


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def pick_engine():
    """Engine identifiers moved around between 4.x and 5.x. Try in order."""
    prop = bpy.types.RenderSettings.bl_rna.properties["engine"]
    available = [e.identifier for e in prop.enum_items]
    for name in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH"):
        if name in available:
            return name
    return available[0]


def make_plane(name, image_path, depth_path=None, depth_strength=0.35):
    """A textured plane, subdivided and displaced if a depth map exists."""
    img = bpy.data.images.load(str(image_path))
    w, h = img.size
    aspect = w / h

    subdiv = 200 if depth_path else 1
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=subdiv, y_subdivisions=subdiv,
                                    size=2.0, location=(0, 0, 0))
    plane = bpy.context.object
    plane.name = name
    plane.scale = (aspect, 1.0, 1.0)

    mat = bpy.data.materials.new(f"mat_{name}")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.extension = "EXTEND"
    emit = nt.nodes.new("ShaderNodeEmission")       # flat: the photo IS the light
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tex.outputs["Color"], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    plane.data.materials.append(mat)

    if depth_path and Path(depth_path).exists():
        dimg = bpy.data.images.load(str(depth_path))
        dtex = bpy.data.textures.new(f"depth_{name}", type="IMAGE")
        dtex.image = dimg
        mod = plane.modifiers.new("depth", type="DISPLACE")
        mod.texture = dtex
        mod.texture_coords = "UV"
        mod.strength = depth_strength
        mod.mid_level = 0.5
        mod.direction = "Z"
    return plane


def setup_camera(scene, focal_mm=50.0):
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = focal_mm
    cam_data.sensor_width = 36.0
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.rotation_euler = (0.0, 0.0, 0.0)
    return cam


def distance_for(scale, focal_mm, sensor=36.0, plane_half_w=1.0):
    """How far back must the camera sit so the framed window is `scale`?"""
    fov = 2.0 * math.atan(sensor / (2.0 * focal_mm))
    return (plane_half_w / scale) / math.tan(fov / 2.0)


def animate(cam, plane, windows, fps, duration, focal_mm, use_dof, aspect):
    """Key the camera from the same (cx, cy, scale, roll) the 2D path uses."""
    n = max(2, int(round(duration * fps)))
    for i in range(n):
        t = i / (n - 1)
        w = windows(t)
        d = distance_for(w["scale"], focal_mm, plane_half_w=aspect)
        # Normalised centre -> Blender units on the plane.
        x = (w["cx"] - 0.5) * 2.0 * aspect
        y = -(w["cy"] - 0.5) * 2.0
        cam.location = (x, y, d)
        cam.rotation_euler = (0.0, 0.0, math.radians(w["roll"]))
        cam.keyframe_insert("location", frame=i + 1)
        cam.keyframe_insert("rotation_euler", frame=i + 1)
        if use_dof:
            cam.data.dof.use_dof = True
            cam.data.dof.focus_distance = d
            cam.data.dof.aperture_fstop = 2.8
            cam.data.dof.keyframe_insert("focus_distance", frame=i + 1)

    for fc in cam.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"   # easing already baked in by moves.py


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--shot", default=None, help="render only this shot id")
    ap.add_argument("--focal", type=float, default=50.0)
    ap.add_argument("--dof", action="store_true")
    ap.add_argument("--samples", type=int, default=16)
    args = ap.parse_args(argv)

    project = Path(args.project).resolve()
    sys.path.insert(0, str(project.parent.parent))
    from ffilm.moves import choose_moves, window_at        # noqa: E402
    from ffilm.spec import Film                            # noqa: E402

    film = Film.load(project / "film.yaml")
    choose_moves(film.shots)

    for shot in film.shots:
        if args.shot and shot.id != args.shot:
            continue
        if shot.kind != "still":
            print(f"  skip {shot.id}: video shots stay on the fast path")
            continue

        clear_scene()
        scene = bpy.context.scene
        scene.render.engine = pick_engine()
        scene.render.resolution_x = film.width
        scene.render.resolution_y = film.height
        scene.render.fps = film.fps
        scene.render.film_transparent = False
        scene.render.use_motion_blur = True
        try:
            scene.eevee.taa_render_samples = args.samples
        except AttributeError:
            pass

        src = film.resolve(shot.src)
        depth = project / "analysis" / "depth" / (src.stem + ".png")
        plane = make_plane(shot.id, src, depth if depth.exists() else None)
        aspect = plane.scale[0]

        cam = setup_camera(scene, args.focal)
        animate(cam, plane,
                lambda t: vars(window_at(shot, t)),
                film.fps, shot.duration, args.focal,
                args.dof and depth.exists(), aspect)

        outdir = project / "out" / "blender" / shot.id
        outdir.mkdir(parents=True, exist_ok=True)
        scene.frame_start = 1
        scene.frame_end = max(2, int(round(shot.duration * film.fps)))
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = str(outdir) + "/f"
        print(f"  rendering {shot.id} -> {outdir}"
              f"{'  [with depth]' if depth.exists() else ''}")
        bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
