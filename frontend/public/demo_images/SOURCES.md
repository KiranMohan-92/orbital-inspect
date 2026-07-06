# Demo image sources

| File | Subject | Source | License |
|---|---|---|---|
| `iss_solar_panel.jpg` | ISS P6 solar array wing tear, STS-120 (2007) | [Wikimedia Commons: STS-120 SAW tear.jpg](https://commons.wikimedia.org/wiki/File:STS-120_SAW_tear.jpg) (NASA) | Public domain (NASA) |
| `hubble_solar_array.jpg` | Retrieved Hubble solar array close-up | [Wikimedia Commons: Solar Array (sa2).jpg](https://commons.wikimedia.org/wiki/File:Solar_Array_%28sa2%29.jpg) (NASA/ESA) | Public domain (NASA) |
| `sentinel_1a.jpg` | Sentinel-1A solar array particle impact, onboard camera (2016) | [ESA: Sentinel-1 impact](https://www.esa.int/Space_Safety/Space_Debris/Copernicus_Sentinel-1A_satellite_hit_by_space_particle) | CC BY-SA 3.0 IGO (ESA) |

Images are downscaled to ≤1600px width for repo size. They serve two purposes:

1. Frontend demo preview (served from this `public/` dir at `/demo_images/<id>.jpg`).
2. Backend demo pipeline input — copy into `backend/data/demo_images/` via `scripts/setup_demo_assets.sh`.
