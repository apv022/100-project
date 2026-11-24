// Renders ONE part for STL export:  openscad -D 'part="disc"' -D idx=0 -o out.stl part.scad
include <parts.scad>
part = "assembly";
idx  = 0;

if (part == "disc")          disc(idx);
else if (part == "hopper")   hopper(idx);
else if (part == "deck")     deck();
else if (part == "base_plate") base_plate();
else if (part == "post")     post();
else if (part == "chute")    rotate([180, 0, 0]) chute();                                   // top face on the bed
else if (part == "cup_holder") cup_holder();
else if (part == "front_panel") translate([0, 0, y_pb]) rotate([-90, 0, 0]) front_panel(); // lying flat, back down
else if (part == "placeholder_lcd") lcd_placeholder();
else if (part == "placeholder_pad") pad_placeholder();
