# Nearby nebulae: positions, distance limits and appearance

These four entries add real nearby clouds to the existing J2000 star reference. Their catalogue identity, approximate distance and direction are sourced below. The three-dimensional shapes, thicknesses, density textures, rotations and display opacity are illustrative. No survey-derived 3D gas reconstruction or radiative-transfer simulation is claimed. All axes in astronomy.json are **semi-axes in light-years**. Cloud fragments beyond 600 light-years from Sol must be clipped by the renderer.

## Pleiades · 昴星团反射云

- Distance: approximately 440 ly. 采用NASA所述约440光年工作值；同页列VLBI约443光年。HYG旧Alcyone距离约403光年，不能因此挪动目录恒星或把近似尘埃体积当成实测星团深度。
- Representative J2000 anchor: RA 3.791410 hours, Dec 24.105137 degrees. J2000方向取HYG 4.1 Alcyone / HIP 17702；这是制图锚点，不是测得的尘埃质心。
- Display: 昴星团周围的尘埃散射蓝白星光，形成细薄的反射云。云的位置以Alcyone的天球方向为代表锚点；星团恒星仍保留HYG原始坐标。
- Inferred semi-axes: 12 / 8 / 5 ly. 三维深度、密度分布、轮廓、颜色响应与朝向仅为制图推定；未进行尘埃层析或辐射转移求解。
- Primary references: [source 1](https://science.nasa.gov/solar-system/skywatching/night-sky-network/spot-the-young-stars-of-the-hyades-and-pleiades/), [source 2](https://raw.githubusercontent.com/astronexus/HYG-Database/c7f7f883fe678cc7680169a50ccd7dcc49b060ce/hyg/CURRENT/hygdata_v41.csv).

## Taurus L1495 · 金牛座暗云

- Distance: approximately 450 ly. ESA给出的近似距离为450光年；L1495/B213研究讨论约10 pc的长结构，三维厚度与本图各半轴仍为推定。
- Representative J2000 anchor: RA 4.301667 hours, Dec 27.616667 degrees. J2000代表坐标取Hacar等2013研究的CDS对象表：04h18.1m,+27°37′。
- Display: L1495的冷尘埃沿细长结构聚集，主要遮暗更远处的星光。这里用不规则暗纹表现云脊，不把Herschel和Planck的红外伪彩画成肉眼可见的红色发光气体。
- Inferred semi-axes: 17 / 5 / 7 ly. 三维深度、密度分布、轮廓、颜色响应与朝向仅为制图推定；未进行尘埃层析或辐射转移求解。
- Primary references: [source 1](https://www.esa.int/ESA_Multimedia/Images/2020/06/Taurus_Molecular_Cloud_viewed_by_Herschel_and_Planck), [source 2](https://cdsarc.cds.unistra.fr/viz-bin/ReadMe/J/A%2BA/554/A55?format=html&tex=true), [source 3](https://www.eso.org/public/images/eso1209d/).

## Rho Ophiuchi · 蛇夫座ρ复合云

- Distance: approximately 390 ly. 采用NASA当前Webb指南与2024年Chandra/Webb介绍中的约390光年。复合云不是一个薄平面；不同区域和距离研究存在差异，本图不把390标成所有云丝的精确测距。
- Representative J2000 anchor: RA 16.441822 hours, Dec -24.384489 degrees. 代表锚点取NASA Webb compass image的16:26:30.56,-24:23:04.16；这是云内观测视场中心，不是整个复合体的质量中心。
- Display: 暗云、受邻近恒星照亮的尘埃和年轻恒星共处于这片复合云中。可见光表现采用克制的散射光与遮光纹理；Webb红外影像的鲜艳滤镜配色不直接移作自然目视颜色。
- Inferred semi-axes: 13 / 9 / 8 ly. 三维深度、密度分布、轮廓、颜色响应与朝向仅为制图推定；未进行尘埃层析或辐射转移求解。
- Primary references: [source 1](https://science.nasa.gov/asset/webb/rho-ophiuchi-nircam-compass-image/), [source 2](https://www.nasa.gov/image-article/take-a-summer-cosmic-road-trip-with-nasas-chandra-and-webb/).

## Coalsack · 煤袋暗云

- Distance: approximately 600 ly. ESO给出约600光年，正位于本图显示边界。云有真实空间延展；本图只显示推定体积中距Sol不超过600光年的部分，边界外的部分被裁切而非不存在。
- Representative J2000 anchor: RA 12.523450 hours, Dec -63.759764 degrees. 代表锚点为ESO eso1539a视场中心12:31:24.42,-63:45:35.15，位置和体积不宣称是整个Coalsack复合体的测得质心与精确轮廓。
- Display: 煤袋暗云在银河亮带前留下不规则的暗影。所示区域以ESO公开影像中心定位；冷尘埃吸收、散射背景星光，不作为红色自发光星云。
- Inferred semi-axes: 24 / 18 / 12 ly. 三维深度、密度分布、轮廓、颜色响应与朝向仅为制图推定；未进行尘埃层析或辐射转移求解。
- Primary references: [source 1](https://www.eso.org/public/news/eso1539/), [source 2](https://www.eso.org/public/images/eso1539a/).

## Time and optical interpretation

The 2564 and 3094 views use the same present-day observational reference for these clouds; their detailed thousand-year evolution is not known. Betelgeuse is handled separately by the manuscript-defined collapse and luminous remnant data, never duplicated as another real cloud.

Reflection dust can scatter light from nearby stars. Dark molecular material attenuates background starlight; it is not a red self-luminous body. In particular, Herschel/Planck far-infrared and Webb near-infrared filter colours must not be presented as natural visible-light emission. The colours and opacity here are restrained, optical-inspired display choices, not measured RGB values or calibrated extinction in magnitudes. A volume may become hard to see when there are few stars behind it.

The existing HYG 4.1 positions are unchanged. Older catalogue parallaxes need not match modern cluster/cloud distances. The Pleiades entry therefore records its distance source separately from the Alcyone direction anchor; the star itself is not relocated to decorate the nebula. No external photograph or image texture has been copied into these assets.
