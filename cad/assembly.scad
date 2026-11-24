// Open this in OpenSCAD to see the whole machine. Colours are for viewing only.
include <parts.scad>
show_servos = true;   // ghost servos + horns
show_placeholders = true;
show_panel = true;

color("silver") base_plate();
color("dimgray") for (p = post_pos) translate([p[0], p[1], base_t]) post();
color("lightgray") translate([0, 0, deck_z]) deck();
color("orange") translate([0, 0, deck_z]) chute();
color("white") translate([0, chute_yc(), base_t]) cup_holder();
if (show_panel) color("lightblue") front_panel();
for (i = [0:2]) {
  color(["tomato", "deepskyblue", "gold"][i]) translate([unit_x[i], 0, deck_z + deck_t + disc_clear]) rotate(load_angle[i]) disc(i);
  color(["salmon", "skyblue", "khaki"][i], 0.6) translate([unit_x[i], 0, deck_z + deck_t]) hopper(i);
  if (show_servos) color("black", 0.5) translate([unit_x[i], 0, deck_z]) ghost_servo();
}
if (show_placeholders) {
  color("limegreen", 0.7) lcd_placeholder();
  color("purple", 0.7) pad_placeholder();
}
