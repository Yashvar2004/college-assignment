"""Generate original looping CCTV-style MP4 assets. Build dependency: Pillow + imageio-ffmpeg."""
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'apps'/'api'/'media'
W,H,FPS,FRAMES=640,360,15,120
FONT=ImageFont.load_default()

def vehicle(draw,x,y,color,label):
    draw.rounded_rectangle((x,y,x+82,y+34),6,fill=color,outline='#d7e2e5',width=1)
    draw.rectangle((x+16,y-13,x+61,y+5),fill=color,outline='#d7e2e5')
    draw.ellipse((x+10,y+25,x+29,y+44),fill='#0c1114')
    draw.ellipse((x+56,y+25,x+75,y+44),fill='#0c1114')
    draw.rectangle((x+26,y+14,x+63,y+25),fill='#eef1dc')
    draw.text((x+29,y+16),label,fill='#121719',font=FONT)

def frame_junction(i):
    im=Image.new('RGB',(W,H),'#71868b');d=ImageDraw.Draw(im)
    d.rectangle((0,0,W,105),fill='#94afb5');d.rectangle((0,105,W,H),fill='#405158')
    for x in range(0,W,90):d.rectangle((x,65,x+55,105),fill='#263d45');d.rectangle((x+8,78,x+20,91),fill='#d8b95f')
    d.polygon([(0,245),(W,160),(W,360),(0,360)],fill='#2a3337');d.polygon([(235,105),(405,105),(510,360),(100,360)],fill='#303a3e')
    d.line((0,272,W,187),fill='#e8d275',width=4);d.line((310,105,295,360),fill='#e8d275',width=3)
    for n in range(3):vehicle(d,(i*7+n*230)%(W+120)-100,220-n*33,['#bf4939','#d1d6d4','#3186a5'][n],['GJ01XX0001','GJ18BL4420','GJ05KT9021'][n])
    d.rectangle((0,0,W,31),fill='#0b1519');d.text((12,9),'AMD-JN-001  AHMEDABAD RIVERFRONT JUNCTION  SYNTHETIC RECORDED FEED',fill='#e9f0f2',font=FONT)
    d.text((530,334),f'T+{i/FPS:04.1f}s',fill='#dbe4e6',font=FONT);return im

def frame_checkpoint(i):
    im=Image.new('RGB',(W,H),'#8d846f');d=ImageDraw.Draw(im)
    d.rectangle((0,0,W,92),fill='#b4c4c0');d.rectangle((0,92,W,H),fill='#56564f')
    d.rectangle((0,105,230,178),fill='#273b42');d.text((30,125),'RTO CHECKPOINT 07',fill='#f0c95f',font=FONT)
    d.rectangle((440,78,560,195),fill='#34484d');d.rectangle((458,104,485,137),fill='#c7e4e5');d.rectangle((510,104,537,137),fill='#c7e4e5')
    d.polygon([(0,255),(W,195),(W,360),(0,360)],fill='#34393a');d.line((0,280,W,220),fill='#eee1a1',width=4)
    bx=230;d.rectangle((bx,178,bx+9,280),fill='#20282b');angle=max(0,55-abs((i%90)-45)*2);endx=bx+190;endy=200-int(angle*.7);d.line((bx+5,195,endx,endy),fill='#e0e3df',width=10)
    x=(i*5)%(W+180)-150;vehicle(d,x,255,'#d3d5cf','GJ01XX0001')
    d.rectangle((0,0,W,31),fill='#0b1519');d.text((12,9),'RTO-CHK-007  SUBHASH BRIDGE RTO  SYNTHETIC RECORDED FEED',fill='#e9f0f2',font=FONT)
    d.text((530,334),f'T+{i/FPS:04.1f}s',fill='#dbe4e6',font=FONT);return im

def encode(name,maker):
    OUT.mkdir(parents=True,exist_ok=True);path=OUT/name
    cmd=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-vcodec','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(path)]
    p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    for i in range(FRAMES):p.stdin.write(maker(i).tobytes())
    p.stdin.close();error=p.stderr.read().decode();code=p.wait()
    if code:raise RuntimeError(error)
    print(f'{path}: {path.stat().st_size/1024:.1f} KiB')

if __name__=='__main__':
    encode('ahmedabad-junction.mp4',frame_junction)
    encode('rto-checkpoint.mp4',frame_checkpoint)
