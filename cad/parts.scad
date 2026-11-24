// All printable parts as modules. Included by assembly.scad and part.scad.
include <params.scad>
$fn = 64;

// 2D pill-shaped slot, long axis along X
module stadium2d(w, l) {
  s = max(l - w, 0) / 2;
  hull() { translate([-s, 0]) circle(d = w); translate([s, 0]) circle(d = w); }
}
module pocket2d(i, extra = 0) {
  stadium2d(pill_d[i] + pocket_clear + extra, pill_len[i] + pocket_clear + extra);
}

// ---------------------------------------------------------------- disc
module disc(i) {
  t = disc_t(i);
  if (t >= 2 * pill_t[i])
    echo(str("WARNING disc ", pill_name[i], ": thickness ", t, " >= 2x pill thickness; two pills could stack"));
  if (pocket_r + (pill_len[i] + pocket_clear) / 2 + 3 > disc_r)
    echo(str("WARNING disc ", pill_name[i], ": pocket too close to the disc edge"));
  difference() {
    cylinder(r = disc_r, h = t);
    // pocket: through hole, deck is the floor.  Pocket sits at angle 0.
    translate([pocket_r, 0, -1]) linear_extrude(t + 2) pocket2d(i);
    // cross cutout for the servo horn (rotated 45 deg so it clears the pocket)
    translate([0, 0, -1]) linear_extrude(horn_pocket_depth + 1) rotate(45)
      for (a = [0, 90]) rotate(a) square([horn_len + horn_tol, horn_arm_w + horn_tol], center = true);
    translate([0, 0, -1]) cylinder(d = horn_screw_d, h = t + 2);
  }
}

// -------------------------------------------------------------- hopper
// Origin = unit centre on the deck top. Print as shown (roof needs supports).
module hopper(i) {
  zc  = disc_clear + disc_t(i) + hopper_gap;       // underside of the roof
  ow  = pill_d[i] + pocket_clear + 2 * outlet_margin;
  ol  = pill_len[i] + pocket_clear + 2 * outlet_margin;
  a   = load_angle[i];
  run = hopper_top_r + pocket_r - ol / 2;
  h   = max(hopper_min_h, run * tan(hopper_wall_angle));
  ty  = skirt_ro + tab_len / 2;                    // tab screw position
  difference() {
    union() {
      cylinder(r = skirt_ro, h = zc + wall);       // skirt + roof
      hull() {                                     // funnel outer
        translate([0, 0, zc + wall - 0.01]) rotate(a) translate([pocket_r, 0, 0])
          linear_extrude(0.01) offset(delta = wall) stadium2d(ow, ol);
        translate([0, 0, zc + wall + h]) cylinder(r = hopper_top_r, h = 0.01);
      }
      for (s = [-1, 1])                            // screw tabs front/back
        translate([-tab_w / 2, s > 0 ? skirt_ro - 1 : -skirt_ro - tab_len, 0])
          cube([tab_w, tab_len + 1, tab_t]);
      translate([-label_w / 2, -skirt_ro + 3, zc + wall - 0.01])  // label plate
        cube([label_w, 1.6, label_h]);
    }
    translate([0, 0, -0.01]) cylinder(r = disc_r + side_clear, h = zc + 0.01);   // disc cavity
    hull() {                                       // pill funnel inside
      translate([0, 0, zc - 0.5]) rotate(a) translate([pocket_r, 0, 0])
        linear_extrude(0.01) stadium2d(ow, ol);
      translate([0, 0, zc + wall + h + 0.5]) cylinder(r = hopper_top_r - wall, h = 0.01);
    }
    for (s = [-1, 1]) translate([0, s * ty, -1]) cylinder(d = screw_clear, h = tab_t + 2);
  }
}

// ---------------------------------------------------------------- deck
// Origin: underside at z=0, shaft of the centre unit at x=0. Servos hang below.
module deck_outline() {
  translate([-deck_w / 2, y_front]) square([deck_w, y_back - y_front]);
  for (s = [-1, 1])                                 // ears reach forward to the front posts
    translate([s > 0 ? lcd_out_w / 2 + 3 : -deck_w / 2, y_pb]) square([deck_w / 2 - lcd_out_w / 2 - 3, y_front - y_pb + 1]);
}
function chute_box() = let(
    hh = (max(pill_len) + pocket_clear + exit_clear) / 2,
    xs = [for (i = [0:2]) exit_pos(i)[0]], ys = [for (i = [0:2]) exit_pos(i)[1]])
  [min(xs) - hh - chute_margin, max(xs) + hh + chute_margin,
   min(ys) - hh - chute_margin, max(ys) + hh + chute_margin];
function chute_tabs() = let(b = chute_box(), yc = (b[2] + b[3]) / 2)
  [[-45, b[2] - 4], [45, b[2] - 4], [b[0] - 4, yc], [b[1] + 4, yc]];

module deck() {
  ty = skirt_ro + tab_len / 2;
  difference() {
    linear_extrude(deck_t) deck_outline();
    for (i = [0:2]) translate([unit_x[i], 0, 0]) {
      translate([0, 0, -1]) cylinder(d = servo_boss_d, h = deck_t + 2);                 // gear boss
      translate([-(servo_w + servo_tol) / 2, servo_body_y - (servo_l + servo_tol) / 2, -1])
        cube([servo_w + servo_tol, servo_l + servo_tol, servo_top_above_ear + servo_tol + 1]); // servo pocket
      for (s = [-1, 1]) translate([0, servo_body_y + s * servo_ear_hole_span / 2, -1])
        cylinder(d = 1.6, h = 7);                                                       // ear screws
      rotate(exit_angle[i]) translate([pocket_r, 0, -1])
        linear_extrude(deck_t + 2) pocket2d(i, exit_clear);                              // exit hole
      for (s = [-1, 1]) translate([0, s * ty, deck_t - 6]) cylinder(d = screw_pilot, h = 7); // hopper screws
    }
    for (p = post_pos) translate([p[0], p[1], -1]) cylinder(d = screw_clear, h = deck_t + 2);
    for (t = chute_tabs()) translate([t[0], t[1], -1]) cylinder(d = screw_pilot, h = 6);
  }
}

// ---------------------------------------------------------- base plate
module base_plate() {
  difference() {
    translate([-deck_w / 2, y_pb, 0]) cube([deck_w, y_back - y_pb, base_t]);
    for (p = post_pos) translate([p[0], p[1], -1]) cylinder(d = screw_clear, h = base_t + 2);
    translate([-cable_w / 2, y_back - 20, -1]) cube([cable_w, 10, base_t + 2]);
    for (sx = [-1, 1]) translate([sx * 60, y_pb - 1, base_t / 2]) rotate([-90, 0, 0])
      cylinder(d = screw_pilot, h = 12);                                                // panel screws
  }
}

// ---------------------------------------------------------------- post
module post() {
  difference() {
    cylinder(d = post_d, h = deck_h);
    for (z = [-1, deck_h - 9]) translate([0, 0, z]) cylinder(d = screw_pilot, h = 10);
    for (z = [30, 70]) translate([0, -post_d / 2 - 1, z]) rotate([-90, 0, 0]) cylinder(d = screw_pilot, h = 10);
  }
}

// --------------------------------------------------------------- chute
// Origin: top (flush with deck underside) at z=0, falling to z=-chute_drop.
module chute() {
  b = chute_box();  yc = (b[2] + b[3]) / 2;
  ol = b[3] - b[2] - 2 * chute_wall;
  module slab(x0, x1, y0, y1, z) translate([x0, y0, z]) cube([x1 - x0, y1 - y0, 0.01]);
  difference() {
    union() {
      hull() {
        slab(b[0], b[1], b[2], b[3], -0.01);
        slab(-outlet_w / 2 - chute_wall, outlet_w / 2 + chute_wall, yc - ol / 2 - chute_wall, yc + ol / 2 + chute_wall, -chute_drop);
      }
      for (t = chute_tabs()) translate([t[0] - 5, t[1] - 5, -tab_t]) cube([10, 10, tab_t]);
    }
    hull() {
      slab(b[0] + chute_wall, b[1] - chute_wall, b[2] + chute_wall, b[3] - chute_wall, 0.5);
      slab(-outlet_w / 2, outlet_w / 2, yc - ol / 2, yc + ol / 2, -chute_drop - 0.5);
    }
    for (t = chute_tabs()) translate([t[0], t[1], -tab_t - 1]) cylinder(d = screw_clear, h = tab_t + 2);
  }
}
function chute_yc() = (chute_box()[2] + chute_box()[3]) / 2;

// ---------------------------------------------------------- cup holder
module cup_holder() {
  difference() {
    cylinder(d = cup_d + 2 * wall + 2 * cup_clear, h = cup_holder_h);
    translate([0, 0, 2]) cylinder(d = cup_d + 2 * cup_clear, h = cup_holder_h);
    translate([-cup_d * 0.3, -cup_d, 2]) cube([cup_d * 0.6, cup_d, cup_holder_h]);   // open at the front
  }
}

// --------------------------------------------------- front panel (world)
module panel_cut(cx, cz, w, h) translate([cx - w / 2, y_pb - panel_t - 1, cz - h / 2]) cube([w, panel_t + 2, h]);
module panel_recess(cx, cz, w, h) translate([cx - w / 2, y_pb - lcd_recess, cz - h / 2]) cube([w, lcd_recess + 1, h]);

module front_panel() {
  difference() {
    translate([-deck_w / 2, y_pb - panel_t, 0]) cube([deck_w, panel_t, panel_h]);
    panel_cut(0, lcd_cz, lcd_view_w, lcd_view_h);          // LCD window
    panel_recess(0, lcd_cz, lcd_out_w, lcd_out_h);         // LCD module pocket (rear)
    panel_cut(pad_cx, pad_cz, pad_w, pad_h);               // button pad window
    panel_cut(0, 6 + cup_win_h / 2, cup_win_w, cup_win_h); // cup opening
    for (sx = [-1, 1]) {
      for (z = [30, 70]) translate([sx * post_x, y_pb - panel_t - 1, z]) rotate([-90, 0, 0]) cylinder(d = screw_clear, h = panel_t + 2);
      translate([sx * 60, y_pb - panel_t - 1, base_t / 2]) rotate([-90, 0, 0]) cylinder(d = screw_clear, h = panel_t + 2);
    }
  }
}

// placeholders for fit checks (not for printing)
module lcd_placeholder() translate([-lcd_out_w / 2, y_pb, lcd_cz - lcd_out_h / 2]) cube([lcd_out_w, lcd_depth, lcd_out_h]);
module pad_placeholder() translate([pad_cx - pad_w / 2, y_pb, pad_cz - pad_h / 2]) cube([pad_w, pad_depth, pad_h]);

module ghost_servo() {   // origin: shaft axis, ear top (deck underside) at z=0
  translate([-servo_w / 2, servo_body_y - servo_l / 2, -servo_below_ear]) cube([servo_w, servo_l, servo_below_ear + servo_top_above_ear]);
  translate([-servo_w / 2, servo_body_y - servo_ear_span / 2, -2.4]) cube([servo_w, servo_ear_span, 2.4]);
  cylinder(d = 5, h = horn_bottom_above_ear);
  translate([0, 0, horn_bottom_above_ear]) linear_extrude(horn_h) rotate(45)
    for (a = [0, 90]) rotate(a) square([horn_len, horn_arm_w], center = true);
}
