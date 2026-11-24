// =====================================================================
//  PILL DISPENSER - PARAMETERS.  Everything you may want to tweak is here.
//  All units are millimetres.  Edit, then run ./export.sh (or open
//  assembly.scad in OpenSCAD to look at it).  You can also override from
//  the command line:  openscad -D 'pill_d=[9,7,6]' ...
// =====================================================================

// ---------- PILLS (unit order: A, B, C = left, centre, right) ----------
pill_name = ["A", "B", "C"];
pill_d    = [8, 7, 6];      // DIAMETER / width of each pill
pill_len  = [8, 12, 6];     // LENGTH of each pill (= diameter for round pills)
pill_t    = [4, 5, 3.5];    // THICKNESS (height) of each pill lying flat
                            // ^ placeholder sizes: measure the real pills!

pocket_clear        = 1.0;  // extra room around the pill in the disc pocket
pocket_depth_factor = 1.4;  // pocket depth = factor * pill_t (keep < 2 so two can't stack)
exit_clear          = 1.0;  // extra room of the exit hole over the pocket

// ---------- DISC + HOPPER ----------
disc_d      = 70;           // disc diameter
pocket_r    = 24;           // distance from shaft to pocket centre
disc_clear  = 0.3;          // gap between disc and the deck it slides on
side_clear  = 1.2;          // gap between disc edge and hopper skirt
wall        = 2.0;          // general wall thickness (>= 1.6 for a 0.4 nozzle)
unit_gap    = 1.6;          // gap between neighbouring hoppers
hopper_gap  = 0.6;          // gap between disc top and hopper roof: smaller than
                            // any pill's thickness so pills can't wedge underneath
hopper_top_r      = 27;     // radius of the top opening you pour pills into
hopper_wall_angle = 50;     // steepness of the funnel (45 or more; steeper = taller)
hopper_min_h      = 30;     // minimum funnel height
outlet_margin     = 1.5;    // funnel outlet is the pocket + this on every side
tab_len = 10;  tab_w = 12;  tab_t = 3;   // hopper screw tabs
label_w = 24;  label_h = 14;             // flat label plate on each hopper

// Rotation. A servo turns each disc by `throw` degrees between the LOAD spot
// (pocket under the hopper) and the EXIT spot (pocket over the hole).
// Angles are measured from above: 0 = +X (right), 90 = back, 270 = front.
// Keep |load - exit| = throw (mod 360).  Servo angles go in config.py.
throw      = 120;
load_angle = [60, 30, 120];
exit_angle = [300, 270, 240];   // all three exit toward the front/centre

// ---------- SERVO (SG90 / MG90S class) ----------
servo_w = 12.2;  servo_l = 22.8;       // body footprint
servo_ear_span = 32.5;  servo_ear_hole_span = 27.8;
servo_shaft_end = 5.9;                 // shaft centre to nearest body end
servo_top_above_ear = 6.5;             // body above the ears (goes into the deck)
servo_below_ear = 16.2;                // body below the ears
servo_boss_d = 12.5;                   // hole for the round gear boss
servo_tol = 0.3;
horn_bottom_above_ear = 9.0;           // where the horn sits
horn_h = 3.5;  horn_len = 36;  horn_arm_w = 4.6;  horn_tol = 0.4;
horn_screw_d = 2.4;

// ---------- FRAME ----------
base_t   = 4;        // base plate thickness
deck_h   = 80;       // height from base plate to deck underside (servos + chute live here)
deck_floor = 1.8;    // deck material above the servo pocket
post_d   = 12;
screw_clear = 3.4;   // M3 clearance hole
screw_pilot = 2.6;   // M3 self-tapping pilot hole
chute_drop   = 50;   // how far the chute falls (>= ~35 deg slope)
chute_wall   = 2.0;
chute_margin = 4;    // chute oversize around the exit holes
outlet_w     = 24;   // chute outlet width
cable_w = 60;        // cable slot in the base plate

// ---------- CUP ----------
cup_d = 45;  cup_h = 26;  cup_clear = 1.0;  cup_holder_h = 10;

// ---------- FRONT PANEL (rough placeholders - set to your real parts) ----------
panel_t = 4;  panel_h = 175;
lcd_view_w = 155;  lcd_view_h = 86;        // visible screen window
lcd_out_w  = 194;  lcd_out_h  = 110;       // whole module (7" official touchscreen)
lcd_depth  = 20;
lcd_recess = 2;                            // rear pocket depth for the module
pad_w = 60;  pad_h = 40;  pad_depth = 10;  // button pad placeholder
cup_win_w = 70;  cup_win_h = 32;           // opening where the cup slides out

// =========== DERIVED (don't edit below) ===========
disc_r   = disc_d / 2;
skirt_ro = disc_r + side_clear + wall;
pitch    = 2 * skirt_ro + unit_gap;
unit_x   = [-pitch, 0, pitch];
deck_w   = 2 * pitch + 2 * skirt_ro + 12;

deck_t   = servo_top_above_ear + servo_tol + deck_floor;
servo_body_y = servo_l / 2 - servo_shaft_end;      // body centre, shaft at origin
horn_bottom_above_deck = horn_bottom_above_ear - deck_t;
horn_pocket_depth = horn_bottom_above_deck + horn_h + horn_tol - disc_clear;
disc_min_t = max(4, horn_pocket_depth + 1.4);

y_back  = skirt_ro + tab_len + 6;
y_front = -y_back;
y_pb    = y_front - (lcd_depth + 6);               // panel back face
post_x  = deck_w / 2 - post_d / 2 - 3;
post_pos = [[-post_x, y_pb + post_d / 2], [post_x, y_pb + post_d / 2],
            [-post_x, y_back - post_d / 2 - 1], [post_x, y_back - post_d / 2 - 1]];
deck_z  = base_t + deck_h;                         // deck underside, world z
lcd_cz  = panel_h - lcd_out_h / 2 - 8;
pad_cx  = cup_win_w / 2 + 15 + pad_w / 2;
pad_cz  = pad_h / 2 + 8;

function pocket_depth(i) = pocket_depth_factor * pill_t[i];
function disc_t(i)       = max(disc_min_t, pocket_depth(i));
function exit_pos(i)     = [unit_x[i] + pocket_r * cos(exit_angle[i]), pocket_r * sin(exit_angle[i])];
