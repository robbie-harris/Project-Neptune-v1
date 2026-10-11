import hashlib
import io
import json
import zipfile

import cv2
import numpy as np
import pytest
from PIL import Image

from verify_roboflow_export import verify


def fixture_export(tmp_path, failure=None):
    data = tmp_path/'data'; data.mkdir(); records=[]
    archive = tmp_path/'export.zip'
    pixels = np.random.default_rng(42).integers(0,256,(48,64,3),dtype=np.uint8) if failure in ('jpeg','jpeg-change') else np.full((48,64,3), 80, np.uint8)
    _, png = cv2.imencode('.png', pixels); raw=png.tobytes()
    with zipfile.ZipFile(archive,'w') as z:
        for i, split in enumerate(('train','val','test')):
            key=f'o{i:03d}_v00'; image=data/f'{key}.png'; image.write_bytes(raw)
            positive=i != 2
            records.append({'id':key,'split':split,'image':image.name,'width':64,'height':48,
                            'bbox':[10,12,30,22] if positive else None,
                            'sha256':hashlib.sha256(raw).hexdigest()})
            folder='valid' if split=='val' else split
            filename=f'{key}.png.rf.example.png'
            exported_raw = raw
            if failure in ('jpeg','jpeg-change'):
                filename=f'{key}.png.rf.example.jpg'
                rendered=pixels if failure=='jpeg' else np.clip(pixels.astype(int)+10,0,255).astype(np.uint8)
                buffer=io.BytesIO(); Image.fromarray(cv2.cvtColor(rendered,cv2.COLOR_BGR2RGB)).save(buffer,format='JPEG',quality=65)
                exported_raw=buffer.getvalue()
            annotations=[{'image_id':i,'category_id':14,'bbox':[10,12,20,10]}] if positive else []
            if failure=='box' and i==0: annotations[0]['bbox'][0]=20
            if failure=='negative' and i==2: annotations=[{'image_id':i,'category_id':14,'bbox':[10,12,20,10]}]
            dims=(64,48) if failure!='resize' or i!=0 else (32,24)
            coco={'categories':[{'id':14,'name':'pipe'}], 'images':[{'id':i,'file_name':filename,'width':dims[0],'height':dims[1]}], 'annotations':annotations}
            z.writestr(f'{folder}/_annotations.coco.json',json.dumps(coco));z.writestr(f'{folder}/{filename}',exported_raw)
    (data/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
    return data,archive


def test_frozen_export_preserves_sources_and_negatives(tmp_path):
    report=verify(*fixture_export(tmp_path))
    assert report['images']==3 and report['exact_source_hash_matches']==3
    assert report['negative_counts']=={'test':1}


@pytest.mark.parametrize('failure',['box','negative','resize'])
def test_export_rejects_changed_labels_or_dimensions(tmp_path,failure):
    with pytest.raises(ValueError): verify(*fixture_export(tmp_path,failure))


def test_native_jpeg_compression_is_reproduced_without_relaxing_pixels(tmp_path):
    report=verify(*fixture_export(tmp_path,'jpeg'))
    assert report['exactly_reproduced_jpeg_images']==3
    assert report['maximum_reencoding_pixel_mae']>3


def test_jpeg_of_changed_pixels_is_rejected(tmp_path):
    with pytest.raises(ValueError,match='reencoding'): verify(*fixture_export(tmp_path,'jpeg-change'))
