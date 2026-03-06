# Model Weights Analysis & Status

## Test Results Summary

✅ **Good News:**
- PyTorch is installed (version 2.9.1+cpu)
- Weights file exists at: `C:/Users/Anas/Downloads/ots_train_ffa_3_19.pk`
- File can be loaded by PyTorch
- Model architecture loads successfully
- Model inference works (tested with dummy image)

⚠️ **Issue Found:**
The weights file structure is **NOT in the expected format**. 

### Current File Structure:
```
{
  'step': <training step number>,
  'max_psnr': <peak PSNR value>,
  'max_ssim': <peak SSIM value>,
  'ssims': <list of SSIM values>,
  'psnrs': <list of PSNR values>,
  ... (2 more keys)
}
```

**Problem:** These are **training metrics/logs**, NOT model weights!

### Expected Format:
The code expects either:
1. A file with `state_dict` key containing model parameters:
   ```python
   {
     'state_dict': {
       'entry.0.weight': <tensor>,
       'entry.0.bias': <tensor>,
       'body.0.block.0.weight': <tensor>,
       ...
     }
   }
   ```

2. Or a direct state_dict:
   ```python
   {
     'entry.0.weight': <tensor>,
     'entry.0.bias': <tensor>,
     ...
   }
   ```

## Current Behavior

**What's happening now:**
1. ✅ Model architecture is created (FFANet)
2. ✅ Weights file is loaded
3. ❌ `model.load_state_dict()` is called with training metrics instead of weights
4. ⚠️ PyTorch silently ignores keys that don't match model parameters
5. ⚠️ **Model is using RANDOM INITIALIZATION** (not trained weights!)
6. ✅ Model still runs inference, but results are poor quality

**This means:** Even though the model "loads", it's **NOT using your trained weights** - it's using random weights!

## Why CLAHE is Used More Often

Even when you select "ffa_net" in the frontend:

1. **If weights don't load properly** → Falls back to CLAHE (this might be happening silently)
2. **If model is None** → Falls back to CLAHE  
3. **Default settings** → Uses CLAHE (`DEHAZE_IMAGE_MODEL=clahe` in .env)

## Solutions

### Option 1: Fix the Weights File Format (Recommended)

You need to extract the actual model weights from your training checkpoint. The `.pk` file might be a training log, not the actual model checkpoint.

**Check if you have:**
- A different file with `.pth` or `.pt` extension
- A checkpoint file from training (usually saved separately)
- The actual model weights saved during training

**If you have the correct weights file:**
1. Update `.env`:
   ```env
   DEHAZE_FFA_WEIGHTS=C:/path/to/correct/weights.pth
   ```

### Option 2: Update Code to Handle Your File Format

If your `.pk` file contains the weights under a different key structure, we need to update `models/ffa_net.py` to handle it.

**To find the correct key, run:**
```python
import torch
state = torch.load("C:/Users/Anas/Downloads/ots_train_ffa_3_19.pk", map_location='cpu')
print(state.keys())  # See all keys
# Look for keys like: 'model', 'net', 'weights', or check nested dicts
```

### Option 3: Use Official FFA-Net Weights

Download pre-trained weights from the official repository:
- https://github.com/zhilin007/FFA-Net
- Look for `FFA-Net.pth` or similar checkpoint files

## How to Verify Weights Are Actually Being Used

1. **Check the logs** when backend starts:
   - ✅ Good: `"Loaded FFA-Net model (device=cpu)"` 
   - ⚠️ Bad: `"Failed to load FFA-Net: ..."` or warnings

2. **Test with known hazy image:**
   - If using random weights → poor/no improvement
   - If using trained weights → significant improvement

3. **Check model parameters:**
   ```python
   # If weights loaded correctly, parameters should have meaningful values
   # If random, parameters will be near zero or random
   for name, param in model.named_parameters():
       print(f"{name}: mean={param.mean().item():.6f}, std={param.std().item():.6f}")
   ```

## Current Configuration

From your `.env` file:
- ✅ `DEHAZE_FFA_WEIGHTS=C:/Users/Anas/Downloads/ots_train_ffa_3_19.pk` (file exists)
- ⚠️ `DEHAZE_IMAGE_MODEL=clahe` (defaults to CLAHE)
- ⚠️ `DEHAZE_VIDEO_MODEL=clahe` (defaults to CLAHE)
- ✅ `DEHAZE_FFA_BLEND=0.4` (40% FFA-Net, 60% original when blending)

## Recommendations

1. **Immediate:** Check if you have the actual model weights file (not just training logs)
2. **Update .env:** Set `DEHAZE_IMAGE_MODEL=ffa_net` and `DEHAZE_VIDEO_MODEL=ffa_net` if you want FFA-Net by default
3. **Verify:** Run the test script again after fixing weights to confirm proper loading
4. **Alternative:** Use CLAHE for now (it works reliably) until you get the correct weights file

## Next Steps

1. Inspect your `.pk` file to see if weights are stored under a different key
2. Check if you have other checkpoint files from training
3. If the file format is correct but under different keys, we can update the loading code
4. If you need to download official weights, update the path in `.env`

