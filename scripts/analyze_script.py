from pathlib import Path
# Read server.py and locate the inline script that contains initBalloons
text = Path('server.py').read_text('utf-8')
pos = text.find('initBalloons')
if pos==-1:
    print('initBalloons not found')
    raise SystemExit(1)
# find the opening <script> before pos
start = text.rfind('<script', 0, pos)
if start==-1:
    print('opening <script not found')
    raise SystemExit(1)
# find the '>' end of opening tag
start = text.find('>', start)
end = text.find('</script>', pos)
if start==-1 or end==-1:
    print('script block not found')
    raise SystemExit(1)
block = text[start+1:end]
# Emulate f-string output: replace double braces with single
rendered = block.replace('{{','{').replace('}}','}')
print('---SCRIPT START---')
print(rendered)
print('---SCRIPT END---')
# Check parentheses and braces
pairs = [('(',')'),('{','}'),('[',']')]
for o,c in pairs:
    print(f"{o}{c} counts ->", rendered.count(o), rendered.count(c))
# Find first line where parentheses imbalance occurs by scanning
open_paren = 0
for i,line in enumerate(rendered.splitlines(),1):
    for ch in line:
        if ch=='(':
            open_paren +=1
        elif ch==')':
            open_paren -=1
    if open_paren<0:
        print('paren negative at line', i)
        break
print('final paren balance', open_paren)
open_brace=0
for i,line in enumerate(rendered.splitlines(),1):
    for ch in line:
        if ch=='{': open_brace+=1
        elif ch=='}': open_brace-=1
    if open_brace<0:
        print('brace negative at line', i)
        break
print('final brace balance', open_brace)
