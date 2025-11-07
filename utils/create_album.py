#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import re
from datetime import datetime
from pathlib import Path

# 图像处理库
try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("警告: 未安装PIL/Pillow库，无法压缩图片和提取EXIF")

def sanitize_filename(filename):
    """清理文件名"""
    name = os.path.splitext(filename)[0]
    name = re.sub(r'[^\w\u4e00-\u9fff-]', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')
    return name

def get_photo_datetime(image_path):
    """提取照片拍摄时间"""
    if not PIL_AVAILABLE:
        return ""
    
    try:
        with Image.open(image_path) as img:
            exif_data = img._getexif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag == 'DateTime' or tag == 'DateTimeOriginal':
                        # EXIF时间格式: 2024:11:06 14:30:22
                        try:
                            dt = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                            return dt.strftime('%Y年%m月%d日 %H:%M')
                        except:
                            return value
    except:
        pass
    
    return ""

def compress_to_webp(input_path, output_path, max_width=1920, quality=80):
    """压缩并转换为WebP格式"""
    if not PIL_AVAILABLE:
        print("无法转换为WebP，复制原文件")
        shutil.copy2(input_path, output_path.with_suffix('.jpg'))
        return output_path.with_suffix('.jpg')
    
    try:
        with Image.open(input_path) as img:
            # 转换为RGB模式（WebP需要）
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # 调整尺寸
            width, height = img.size
            if width > max_width:
                ratio = max_width / width
                new_width = max_width
                new_height = int(height * ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # 保存为WebP格式
            webp_path = output_path.with_suffix('.webp')
            img.save(webp_path, 'WEBP', quality=quality, optimize=True)
            
            return webp_path
            
    except Exception as e:
        print(f"转换WebP失败，使用JPEG: {e}")
        try:
            with Image.open(input_path) as img:
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                width, height = img.size
                if width > max_width:
                    ratio = max_width / width
                    new_width = max_width
                    new_height = int(height * ratio)
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                jpg_path = output_path.with_suffix('.jpg')
                img.save(jpg_path, 'JPEG', quality=85, optimize=True)
                return jpg_path
        except:
            # 最后备选方案：直接复制
            fallback_path = output_path.with_suffix('.jpg')
            shutil.copy2(input_path, fallback_path)
            return fallback_path

def create_album():
    # 获取照片目录
    source_dir = input("请输入照片目录路径: ").strip()
    
    # 检查目录
    source_path = Path(source_dir)
    if not source_path.exists():
        print(f"错误: 目录不存在: {source_dir}")
        return False
    
    # 获取图片文件
    image_extensions = {'.jpg', '.jpeg', '.JPG', '.JPEG', '.png', '.PNG', '.webp', '.WEBP'}
    image_files = []
    for ext in image_extensions:
        image_files.extend(source_path.glob(f'*{ext}'))
    
    if not image_files:
        print("没有找到图片文件")
        return False
    
    image_files.sort(key=lambda x: x.name)
    print(f"找到 {len(image_files)} 张照片")
    
    # 生成基本信息
    date_str = datetime.now().strftime('%Y-%m-%d')
    folder_name = source_path.name
    album_slug = f"{folder_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    # 创建目录
    project_root = Path.cwd()
    albums_dir = project_root / 'assets' / 'images' / 'albums' / album_slug
    photo_albums_dir = project_root / '_photo_albums'
    
    albums_dir.mkdir(parents=True, exist_ok=True)
    photo_albums_dir.mkdir(exist_ok=True)
    
    print("开始处理照片...")
    
    # 处理照片
    photos_data = []
    for i, img_file in enumerate(image_files):
        # 提取拍摄时间
        photo_datetime = get_photo_datetime(img_file)
        if photo_datetime:
            print(f"  提取时间: {photo_datetime}")
        
        clean_name = sanitize_filename(img_file.name)
        base_filename = f"{i+1:02d}_{clean_name}"
        target_file = albums_dir / base_filename
        
        # 压缩并转换为WebP
        final_file = compress_to_webp(img_file, target_file)
        
        # 获取相对路径
        relative_path = f"/assets/images/albums/{album_slug}/{final_file.name}"
        photos_data.append({
            'path': relative_path,
            'caption': photo_datetime if photo_datetime else ""
        })
        
        print(f"  {i+1}/{len(image_files)}: {final_file.name}")
    
    # 生成MD文件
    md_content = f"""---
title: ""
description: ""
cover_image: "{photos_data[0]['path']}"
date: {date_str}
location: ""
photographer: ""
tags: []
photos:"""
    
    for photo_data in photos_data:
        md_content += f"""
  - image: "{photo_data['path']}"
    caption: "{photo_data['caption']}"
    """
    
    md_content += """
---

"""
    
    # 保存文件
    md_filename = f"{album_slug}.md"
    md_file_path = photo_albums_dir / md_filename
    
    with open(md_file_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"✅ 完成!")
    print(f"📁 照片: {albums_dir}")
    print(f"📝 文件: {md_file_path}")
    print(f"🌐 URL: /photography/{album_slug}/")
    
    return True

if __name__ == '__main__':
    try:
        create_album()
    except KeyboardInterrupt:
        print("\n取消操作")
    except Exception as e:
        print(f"错误: {e}")