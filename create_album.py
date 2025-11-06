#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import argparse
from datetime import datetime
from pathlib import Path
import re
import json

# EXIF相关库
try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    EXIF_AVAILABLE = True
except ImportError:
    EXIF_AVAILABLE = False
    print("警告: 未安装PIL/Pillow库，无法提取EXIF信息")
    print("安装命令: pip install Pillow")

def sanitize_filename(filename):
    """清理文件名，移除特殊字符"""
    name = os.path.splitext(filename)[0]
    name = re.sub(r'[^\w\u4e00-\u9fff-]', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')
    return name

def get_album_slug(album_title):
    """从标题生成URL友好的slug"""
    slug = re.sub(r'[^\w\u4e00-\u9fff\s-]', '', album_title.lower())
    slug = re.sub(r'[\s_-]+', '-', slug).strip('-')
    return slug

def convert_to_serializable(obj):
    """将EXIF数据转换为可序列化的格式"""
    if hasattr(obj, 'numerator') and hasattr(obj, 'denominator'):
        # 处理 IFDRational 类型
        try:
            return float(obj.numerator) / float(obj.denominator)
        except ZeroDivisionError:
            return 0
    elif isinstance(obj, (list, tuple)):
        return [convert_to_serializable(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: convert_to_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, bytes):
        try:
            return obj.decode('utf-8')
        except UnicodeDecodeError:
            return str(obj)
    else:
        return obj

def decimal_coords(coords, ref):
    """将GPS坐标转换为十进制度数"""
    try:
        decimal_degrees = float(coords[0]) + float(coords[1]) / 60 + float(coords[2]) / 3600
        if ref == "S" or ref == "W":
            decimal_degrees = -decimal_degrees
        return decimal_degrees
    except:
        return None

def get_gps_coordinates(gps_info):
    """从GPS信息中提取坐标"""
    try:
        gps_latitude = gps_info.get("GPSLatitude")
        gps_latitude_ref = gps_info.get('GPSLatitudeRef')
        gps_longitude = gps_info.get('GPSLongitude')
        gps_longitude_ref = gps_info.get('GPSLongitudeRef')
        
        if gps_latitude and gps_latitude_ref and gps_longitude and gps_longitude_ref:
            lat = decimal_coords(gps_latitude, gps_latitude_ref)
            lon = decimal_coords(gps_longitude, gps_longitude_ref)
            if lat is not None and lon is not None:
                return lat, lon
    except Exception as e:
        print(f"GPS解析错误: {e}")
    return None, None

def format_exposure_time(exposure_time):
    """格式化曝光时间"""
    try:
        exposure_float = float(exposure_time)
        if exposure_float < 1:
            return f"1/{int(1/exposure_float)}"
        else:
            return f"{exposure_float:.1f}"
    except:
        return str(exposure_time)

def safe_float(value):
    """安全转换为浮点数"""
    try:
        if hasattr(value, 'numerator') and hasattr(value, 'denominator'):
            return float(value.numerator) / float(value.denominator)
        return float(value)
    except:
        return None

def extract_exif_data(image_path):
    """提取照片EXIF信息"""
    if not EXIF_AVAILABLE:
        return {}
    
    try:
        image = Image.open(image_path)
        exifdata = image.getexif()
        
        if not exifdata:
            return {}
        
        exif_dict = {}
        gps_info = {}
        
        # 提取基本EXIF信息
        for tag_id in exifdata:
            tag = TAGS.get(tag_id, tag_id)
            data = exifdata.get(tag_id)
            
            # 处理GPS信息
            if tag == "GPSInfo":
                try:
                    for gps_tag_id in data:
                        gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                        gps_data = data[gps_tag_id]
                        gps_info[gps_tag] = convert_to_serializable(gps_data)
                except:
                    pass
            else:
                # 转换为可序列化的数据
                converted_data = convert_to_serializable(data)
                exif_dict[tag] = converted_data
        
        # 处理拍摄时间
        datetime_original = exif_dict.get('DateTimeOriginal')
        if datetime_original:
            try:
                # 转换为标准格式
                dt = datetime.strptime(str(datetime_original), '%Y:%m:%d %H:%M:%S')
                exif_dict['DateTimeOriginal'] = dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                print(f"日期解析错误: {e}")
        
        # 处理GPS坐标
        if gps_info:
            lat, lon = get_gps_coordinates(gps_info)
            if lat is not None and lon is not None:
                exif_dict['GPS'] = {
                    'latitude': lat,
                    'longitude': lon,
                    'coordinates': f"{lat:.6f}, {lon:.6f}"
                }
        
        # 处理曝光时间
        exposure_time = exif_dict.get('ExposureTime')
        if exposure_time is not None:
            exif_dict['ExposureTimeFormatted'] = format_exposure_time(exposure_time)
        
        # 处理焦距
        focal_length = safe_float(exif_dict.get('FocalLength'))
        if focal_length is not None:
            exif_dict['FocalLengthFormatted'] = f"{focal_length:.0f}mm"
        
        # 处理光圈
        f_number = safe_float(exif_dict.get('FNumber'))
        if f_number is not None:
            exif_dict['FNumberFormatted'] = f"f/{f_number:.1f}"
        
        # 清理字符串字段
        for key in ['Make', 'Model', 'Software']:
            if key in exif_dict and exif_dict[key]:
                exif_dict[key] = str(exif_dict[key]).strip()
        
        return exif_dict
        
    except Exception as e:
        print(f"警告: 无法提取 {image_path} 的EXIF信息: {e}")
        return {}

def format_exif_for_display(exif_data):
    """格式化EXIF数据用于显示"""
    if not exif_data:
        return ""
    
    info_parts = []
    
    # 相机信息
    make = exif_data.get('Make', '').strip()
    model = exif_data.get('Model', '').strip()
    if make and model:
        camera = f"{make} {model}".strip()
        info_parts.append(f"📷 {camera}")
    
    # 拍摄参数
    params = []
    if exif_data.get('FNumberFormatted'):
        params.append(exif_data['FNumberFormatted'])
    if exif_data.get('ExposureTimeFormatted'):
        params.append(f"{exif_data['ExposureTimeFormatted']}s")
    if exif_data.get('ISOSpeedRatings'):
        params.append(f"ISO{exif_data['ISOSpeedRatings']}")
    if exif_data.get('FocalLengthFormatted'):
        params.append(exif_data['FocalLengthFormatted'])
    
    if params:
        info_parts.append(f"⚙️ {' | '.join(params)}")
    
    # 拍摄时间
    if exif_data.get('DateTimeOriginal'):
        info_parts.append(f"📅 {exif_data['DateTimeOriginal']}")
    
    # GPS信息
    if exif_data.get('GPS'):
        coords = exif_data['GPS']['coordinates']
        info_parts.append(f"📍 {coords}")
    
    return '\n'.join(info_parts) if info_parts else ""

def create_album(source_dir, album_title, description="", date_str="", extract_exif=True):
    """创建照片集"""
    
    # 设置基础路径
    script_dir = Path(__file__).parent
    project_root = script_dir
    
    # 检查是否在Jekyll项目根目录
    if not (project_root / '_config.yml').exists():
        print("警告: 当前目录不是Jekyll项目根目录")
        print("请在包含_config.yml的目录中运行此脚本")
        return False
    
    # 生成album slug
    album_slug = get_album_slug(album_title)
    if not album_slug:
        album_slug = f"album-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # 设置目标目录
    albums_dir = project_root / 'assets' / 'images' / 'albums' / album_slug
    photo_albums_dir = project_root / '_photo_albums'
    
    # 创建目录
    albums_dir.mkdir(parents=True, exist_ok=True)
    photo_albums_dir.mkdir(exist_ok=True)
    
    # 检查源目录
    source_path = Path(source_dir)
    if not source_path.exists():
        print(f"错误: 源目录不存在: {source_dir}")
        return False
    
    # 获取所有jpg/jpeg文件
    image_extensions = {'.jpg', '.jpeg', '.JPG', '.JPEG'}
    image_files = []
    
    for ext in image_extensions:
        image_files.extend(source_path.glob(f'*{ext}'))
    
    if not image_files:
        print(f"错误: 在 {source_dir} 中没有找到jpg/jpeg文件")
        return False
    
    # 按文件名排序
    image_files.sort(key=lambda x: x.name)
    
    print(f"找到 {len(image_files)} 张照片")
    if extract_exif and EXIF_AVAILABLE:
        print("正在提取EXIF信息...")
    
    # 复制照片并生成照片列表
    photos_data = []
    cover_image = ""
    exif_summary = {}
    
    for i, img_file in enumerate(image_files):
        print(f"处理 ({i+1}/{len(image_files)}): {img_file.name}")
        
        # 提取EXIF信息
        exif_data = {}
        if extract_exif and EXIF_AVAILABLE:
            exif_data = extract_exif_data(img_file)
            
            # 收集相机信息用于汇总
            make = exif_data.get('Make', '').strip()
            model = exif_data.get('Model', '').strip()
            if make and model:
                camera = f"{make} {model}".strip()
                exif_summary[camera] = exif_summary.get(camera, 0) + 1
        
        # 生成新文件名
        clean_name = sanitize_filename(img_file.name)
        new_filename = f"{i+1:02d}_{clean_name}.jpg"
        
        # 目标文件路径
        target_file = albums_dir / new_filename
        
        # 复制文件
        shutil.copy2(img_file, target_file)
        
        # 生成相对路径（用于Jekyll）
        relative_path = f"/assets/images/albums/{album_slug}/{new_filename}"
        
        # 第一张图作为封面
        if i == 0:
            cover_image = relative_path
        
        # 生成默认标题（如果有拍摄时间，使用拍摄时间）
        default_caption = f"照片 {i+1}"
        if exif_data.get('DateTimeOriginal'):
            try:
                dt = datetime.strptime(exif_data['DateTimeOriginal'], '%Y-%m-%d %H:%M:%S')
                default_caption = dt.strftime('%m月%d日 %H:%M')
            except:
                pass
        
        # 生成位置信息（如果有GPS）
        location = ""
        if exif_data.get('GPS'):
            location = f"({exif_data['GPS']['coordinates']})"
        
        # 添加到照片数据
        photo_data = {
            'image': relative_path,
            'caption': default_caption,
            'location': location
        }
        
        # 如果有EXIF信息，添加拍摄参数
        if exif_data:
            photo_data['exif'] = exif_data
            exif_info = format_exif_for_display(exif_data)
            if exif_info:
                photo_data['exif_display'] = exif_info
        
        photos_data.append(photo_data)
    
    # 生成日期（优先使用第一张照片的拍摄日期）
    if not date_str:
        if photos_data and photos_data[0].get('exif', {}).get('DateTimeOriginal'):
            try:
                dt = datetime.strptime(photos_data[0]['exif']['DateTimeOriginal'], '%Y-%m-%d %H:%M:%S')
                date_str = dt.strftime('%Y-%m-%d')
            except:
                date_str = datetime.now().strftime('%Y-%m-%d')
        else:
            date_str = datetime.now().strftime('%Y-%m-%d')
    
    # 生成Markdown文件内容
    md_content = f"""---
title: "{album_title}"
description: "{description}"
cover_image: "{cover_image}"
date: {date_str}
photos:"""
    
    for photo in photos_data:
        md_content += f"""
  - image: "{photo['image']}"
    caption: "{photo['caption']}"
    location: "{photo['location']}\""""
        
        # 添加EXIF信息到YAML（用于模板处理）
        if photo.get('exif'):
            exif = photo['exif']
            md_content += f"""
    exif:"""
            
            # 相机信息
            make = exif.get('Make', '').strip()
            model = exif.get('Model', '').strip()
            if make and model:
                camera = f"{make} {model}".strip()
                md_content += f"""
      camera: "{camera}\""""
            
            # 拍摄时间
            if exif.get('DateTimeOriginal'):
                md_content += f"""
      datetime: "{exif['DateTimeOriginal']}\""""
            
            # 拍摄参数
            if exif.get('FNumberFormatted'):
                md_content += f"""
      aperture: "{exif['FNumberFormatted']}\""""
            if exif.get('ExposureTimeFormatted'):
                md_content += f"""
      shutter: "{exif['ExposureTimeFormatted']}s\""""
            if exif.get('ISOSpeedRatings'):
                md_content += f"""
      iso: {exif['ISOSpeedRatings']}"""
            if exif.get('FocalLengthFormatted'):
                md_content += f"""
      focal_length: "{exif['FocalLengthFormatted']}\""""
            
            # GPS信息
            if exif.get('GPS'):
                md_content += f"""
      gps:
        latitude: {exif['GPS']['latitude']}
        longitude: {exif['GPS']['longitude']}
        coordinates: "{exif['GPS']['coordinates']}\""""
    
    md_content += """
---

<!-- 在这里添加照片集的详细描述 -->

这个照片集包含了 {{ page.photos.size }} 张照片。

你可以在这里写关于这个照片集的故事、背景或者任何想要分享的内容。

## 拍摄信息

- **拍摄时间**: {{ page.date | date: "%Y年%m月%d日" }}
- **照片数量**: {{ page.photos.size }} 张
- **主题**: """ + album_title
    
    # 添加相机信息汇总
    if exif_summary:
        md_content += """

## 拍摄设备

"""
        for camera, count in exif_summary.items():
            md_content += f"- **{camera}**: {count} 张\n"
    
    md_content += """

<!-- 如果需要，可以添加更多内容 -->

## 照片详情

{% for photo in page.photos %}
### {{ photo.caption }}

{% if photo.location and photo.location != "" %}
**拍摄地点**: {{ photo.location }}
{% endif %}

{% if photo.exif %}
**拍摄参数**:
{% if photo.exif.camera %}- 相机: {{ photo.exif.camera }}{% endif %}
{% if photo.exif.datetime %}- 时间: {{ photo.exif.datetime }}{% endif %}
{% if photo.exif.aperture %}- 光圈: {{ photo.exif.aperture }}{% endif %}
{% if photo.exif.shutter %}- 快门: {{ photo.exif.shutter }}{% endif %}
{% if photo.exif.iso %}- ISO: {{ photo.exif.iso }}{% endif %}
{% if photo.exif.focal_length %}- 焦距: {{ photo.exif.focal_length }}{% endif %}
{% if photo.exif.gps %}- GPS: {{ photo.exif.gps.coordinates }}{% endif %}
{% endif %}

---
{% endfor %}
"""
    
    # 保存Markdown文件
    md_filename = f"{album_slug}.md"
    md_file_path = photo_albums_dir / md_filename
    
    with open(md_file_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    # 生成EXIF数据的JSON文件（可选，用于调试）
    if extract_exif and photos_data:
        exif_json_path = albums_dir / 'exif_data.json'
        exif_only_data = []
        for photo in photos_data:
            if photo.get('exif'):
                # 确保所有数据都是可序列化的
                clean_exif = convert_to_serializable(photo['exif'])
                exif_only_data.append({
                    'filename': Path(photo['image']).name,
                    'exif': clean_exif
                })
        
        if exif_only_data:
            try:
                with open(exif_json_path, 'w', encoding='utf-8') as f:
                    json.dump(exif_only_data, f, indent=2, ensure_ascii=False)
                print(f"📊 EXIF数据已保存到: {exif_json_path}")
            except Exception as e:
                print(f"警告: 无法保存EXIF JSON文件: {e}")
    
    print(f"\n✅ 照片集创建成功!")
    print(f"📁 照片目录: {albums_dir}")
    print(f"📝 Markdown文件: {md_file_path}")
    print(f"🌐 访问URL: /photography/{album_slug}/")
    
    if extract_exif and EXIF_AVAILABLE:
        print(f"\n📊 EXIF信息提取完成:")
        if exif_summary:
            for camera, count in exif_summary.items():
                print(f"   {camera}: {count} 张照片")
        else:
            print("   未找到相机信息")
    
    print(f"\n📝 接下来你可以:")
    print(f"1. 编辑 {md_filename} 文件")
    print(f"2. 修改照片标题和描述")
    print(f"3. 调整自动生成的拍摄地点信息")
    print(f"4. 完善照片集描述内容")
    print(f"5. 提交并推送到GitHub")
    
    return True

def main():
    parser = argparse.ArgumentParser(description='批量导入照片创建Jekyll照片集（含EXIF信息提取）')
    parser.add_argument('source_dir', help='包含jpg照片的源目录路径')
    parser.add_argument('title', help='照片集标题')
    parser.add_argument('-d', '--description', default='', help='照片集描述')
    parser.add_argument('--date', help='照片集日期 (YYYY-MM-DD格式，默认使用照片EXIF日期或今天)')
    parser.add_argument('--no-exif', action='store_true', help='跳过EXIF信息提取')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Jekyll 照片集批量导入工具 (含EXIF信息提取)")
    print("=" * 60)
    
    if not EXIF_AVAILABLE and not args.no_exif:
        print("\n⚠️  未安装Pillow库，无法提取EXIF信息")
        print("安装命令: pip install Pillow")
        print("或使用 --no-exif 参数跳过EXIF提取\n")
    
    success = create_album(
        source_dir=args.source_dir,
        album_title=args.title,
        description=args.description,
        date_str=args.date,
        extract_exif=not args.no_exif
    )
    
    if success:
        print("\n🎉 导入完成!")
    else:
        print("\n❌ 导入失败!")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())