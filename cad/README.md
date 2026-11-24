# CAD (parametric, OpenSCAD)

Everything is driven by **`params.scad`**. Pill sizes are not final, so change them there and re-export. All units are mm.

```
sudo apt install openscad      # once
./export.sh                    # renders every part to stl/
./export.sh disc               # only parts whose name starts with "disc"
```

STLs for the current placeholder sizes are already in `stl/`. Open `assembly.scad` in OpenSCAD to see the whole machine (`show_servos`, `show_panel`, `show_placeholders` toggle things).

## The numbers you will tweak

In `params.scad`, one entry per pill (A, B, C = left, centre, right):

| Variable | Meaning |
|----------|---------|
| `pill_d` | pill **diameter** (width) |
| `pill_len` | pill **length**; same as `pill_d` for round pills, bigger for oval/capsule (the pocket becomes a slot) |
| `pill_t` | pill thickness lying flat; sets pocket depth and disc thickness |

Current values (8/8/4, 7/12/5, 6/6/3.5) are **placeholders**. The disc, pocket, exit hole, hopper outlet, funnel height and chute width all follow automatically. OpenSCAD prints a `WARNING` if a pill is so thin that two could stack, or the pocket is too close to the disc edge. Other useful knobs: `disc_d`, `pocket_r`, `hopper_top_r`, `hopper_wall_angle`, `chute_drop`, `cup_d`, and the LCD / button pad sizes (`lcd_*`, `pad_*`). Override from the command line without editing: `openscad -D 'pill_d=[9,7,6]' ...`.

## Parts

| STL | Qty | Notes |
|-----|-----|-------|
| `disc_A/B/C` | 1 each | Pocket is a through-hole (the deck is its floor). Cross-shaped cutout presses onto the SG90 horn. PETG preferred. |
| `hopper_A/B/C` | 1 each | Steep funnel with an outlet that exposes only the pocket, label plate on the front, two screw tabs. **Print with supports under the roof.** |
| `deck` | 1 | Servos screw to its underside (body sits in a pocket, shaft through the floor). Holds the exit holes. Print as shown. |
| `base_plate` | 1 | Bottom plate with cable slot. |
| `post_x4` | **4** | 80 mm posts between base and deck. |
| `chute` | 1 | Funnels all three exit holes to one outlet. Exported upside-down so it prints without supports. |
| `cup_holder` | 1 | Ring, open at the front. |
| `front_panel` | 1 | Rough placeholders: LCD window, button pad window, cup opening. Exported lying flat. |
| `placeholders/*` | - | Boxes for fit checks only. Not for printing. |

M3 self-tapping screws are assumed (3.4 mm clearance, 2.6 mm pilot holes). Servo ears use 2 small screws each.

## How it goes together

Base plate, then 4 posts, then the deck on top. Servos screw under the deck. The chute screws to the deck underside, the discs go on the horns, hoppers screw down over them, and the front panel screws to the front posts and base. The LCD module sits between the panel and the deck.

## Check before printing

- **Bed size:** deck, base plate and panel are **244 mm wide**. If your printer is smaller, shrink `disc_d`/`pocket_r` or ask for the plates to be split.
- **Servo dims:** SG90 values are typical. Measure yours (`servo_*`, `horn_*`).
- **Rotation:** discs turn 120 degrees between load and exit. Servo angles in `config.py` match the defaults; confirm direction on the bench.
- Previews: `preview/`. This is a first pass: not test-printed.
