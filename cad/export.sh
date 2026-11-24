#!/usr/bin/env bash
# Render every part to cad/stl/. Needs OpenSCAD (sudo apt install openscad).
# Usage: ./export.sh            all parts
#        ./export.sh disc       only parts whose name starts with "disc"
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
mkdir -p stl stl/placeholders
render() { # name part idx outdir
  [[ -n "${ONLY:-}" && "$1" != "$ONLY"* ]] && return 0
  echo "==> $1"
  openscad -q -D "part=\"$2\"" -D "idx=$3" -o "$4/$1.stl" part.scad
}
ONLY="${1:-}"
for i in 0 1 2; do
  n=$(echo A B C | cut -d' ' -f$((i+1)))
  render "disc_$n" disc $i stl
  render "hopper_$n" hopper $i stl
done
render deck deck 0 stl
render base_plate base_plate 0 stl
render post_x4 post 0 stl            # print 4 of these
render chute chute 0 stl
render cup_holder cup_holder 0 stl
render front_panel front_panel 0 stl
render placeholder_lcd placeholder_lcd 0 stl/placeholders
render placeholder_pad placeholder_pad 0 stl/placeholders
echo "done: $(pwd)/stl"
