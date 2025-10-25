#!/bin/bash
# 需要安装 imagemagick
for img in assets/images/posts/*.{jpg,jpeg,png}; do
  if [ -f "$img" ]; then
    magick "$img" -quality 85 -resize '1200x1200>' "$img"
  fi
done