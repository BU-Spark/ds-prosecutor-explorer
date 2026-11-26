"""Execute every cell in fresh kernels and retain embedded chart outputs."""
from pathlib import Path
import os
import sys
import json
import hashlib
import asyncio
import nbformat
from nbclient import NotebookClient

if sys.platform=='win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

ROOT=Path(__file__).resolve().parent
execution=ROOT/'.execution'
kernel=execution/'kernels'/'county-review-python'
kernel.mkdir(parents=True,exist_ok=True)
(kernel/'kernel.json').write_text(json.dumps(dict(argv=[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],display_name='County review Python',language='python')),encoding='utf8')
os.environ['JUPYTER_PATH']=str(execution)
os.environ['JUPYTER_RUNTIME_DIR']=str(execution/'runtime')
os.environ['IPYTHONDIR']=str(execution/'ipython')
os.environ['MPLCONFIGDIR']=str(execution/'matplotlib')
os.environ['PYDEVD_DISABLE_FILE_VALIDATION']='1'

for slug in sys.argv[1:] or ['berkshire','cape_and_islands']:
    print(f'Preparing {slug} fresh-kernel execution',flush=True)
    path=ROOT/slug/(slug+'_analysis.ipynb')
    notebook=nbformat.read(path,as_version=4)
    def on_cell_start(cell,cell_index,**kwargs):
        if cell.cell_type=='code':print(f'{slug}: running cell {cell_index+1}/{len(notebook.cells)}',flush=True)
    client=NotebookClient(notebook,timeout=1200,kernel_name='county-review-python',resources={'metadata':{'path':str(path.parent)}},allow_errors=False,
        on_cell_start=on_cell_start)
    try:
        client.execute()
    except Exception:
        nbformat.write(notebook,path)
        raise
    nbformat.validate(notebook)
    errors=[o for c in notebook.cells if c.cell_type=='code' for o in c.outputs if o.output_type=='error']
    assert not errors
    assert all(c.execution_count is not None for c in notebook.cells if c.cell_type=='code')
    images=sum('image/png' in o.get('data',{}) for c in notebook.cells if c.cell_type=='code' for o in c.outputs)
    assert images>=8, f'Expected embedded chart outputs, found {images}'
    nbformat.write(notebook,path)
    print(f'{slug}: PASSED; {images} embedded images; {path.stat().st_size:,} bytes',flush=True)
