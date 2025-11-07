import os
from PIL import Image
import argparse
from pathlib import Path
from tqdm import tqdm

def convert_to_webp(source_path, output_path, quality=80):
    """将单个图片转换为webp格式，保持原始方向"""
    # 打开图片并保持方向
    image = Image.open(source_path)
    
    # 获取EXIF数据
    try:
        exif = image.getexif()
        # 获取方向信息
        orientation = exif.get(274)  # 274 是方向标签的ID
        
        # 根据方向进行旋转
        if orientation:
            ORIENTATION_ROTATE_180 = 3
            ORIENTATION_ROTATE_90 = 6
            ORIENTATION_ROTATE_270 = 8
            
            if orientation == ORIENTATION_ROTATE_180:
                image = image.rotate(180, expand=True)
            elif orientation == ORIENTATION_ROTATE_90:
                image = image.rotate(270, expand=True)
            elif orientation == ORIENTATION_ROTATE_270:
                image = image.rotate(90, expand=True)
    except (AttributeError, KeyError, IndexError):
        # 没有EXIF数据，保持原样
        pass
    
    # 如果图片是RGBA模式但没有实际的透明通道，转换为RGB
    if image.mode == 'RGBA' and not has_transparency(image):
        image = image.convert('RGB')
    
    # 保存为webp
    image.save(output_path, 'webp', quality=quality)
    
def has_transparency(image):
    """检查RGBA图片是否真的有透明通道"""
    if image.mode == 'RGBA':
        extrema = image.getextrema()
        if extrema[3][0] < 255:  # 透明通道的最小值小于255
            return True
    return False

def batch_convert(input_dir, quality=80, delete_original=True):
    """批量转换目录下的所有支持的图片格式"""
    # 支持的图片格式
    supported_formats = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff'}
    
    # 获取所有图片文件
    image_files = []
    for format in supported_formats:
        image_files.extend(Path(input_dir).glob(f'*{format}'))
        image_files.extend(Path(input_dir).glob(f'*{format.upper()}'))
    
    if not image_files:
        print("没有找到支持的图片文件！")
        return
    
    print(f"找到 {len(image_files)} 个图片文件")
    
    # 转换所有图片
    success_count = 0
    error_files = []
    deleted_count = 0
    
    for source_path in tqdm(image_files, desc="转换进度"):
        try:
            # 构建输出文件路径（与源文件相同位置）
            output_path = source_path.parent / f"{source_path.stem}.webp"
            
            # 转换图片
            convert_to_webp(source_path, output_path, quality)
            success_count += 1
            
            # 如果转换成功且需要删除原文件
            if delete_original:
                source_path.unlink()  # 删除原文件
                deleted_count += 1
            
        except Exception as e:
            error_files.append((source_path, str(e)))
            continue
    
    # 打印结果
    print("\n转换完成！")
    print(f"成功转换: {success_count}/{len(image_files)} 个文件")
    if delete_original:
        print(f"已删除原始文件: {deleted_count} 个")
    
    if error_files:
        print("\n以下文件转换失败:")
        for file, error in error_files:
            print(f"- {file.name}: {error}")

def main():
    parser = argparse.ArgumentParser(description='批量将图片转换为webp格式并删除原文件')
    parser.add_argument('input_dir', help='输入目录路径')
    parser.add_argument('--quality', type=int, default=80, help='webp质量（0-100，默认80）')
    parser.add_argument('--keep-original', action='store_true', help='保留原始文件（默认会删除）')
    
    args = parser.parse_args()
    
    # 询问用户确认
    if not args.keep_original:
        response = input("此操作将删除原始图片文件！是否继续？(y/n): ")
        if response.lower() != 'y':
            print("操作已取消")
            return
    
    batch_convert(args.input_dir, args.quality, not args.keep_original)

if __name__ == '__main__':
    main()