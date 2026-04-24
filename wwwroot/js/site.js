(() => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) return;

    const targets = Array.from(document.querySelectorAll('.background-image'));
    if (!targets.length) return;

    const moveStrength = 50;
    const signedSquare = (value) => value * Math.abs(value);
    const randomVector = () => {
        const angle = Math.random() * Math.PI * 2;
        return { x: Math.cos(angle), y: Math.sin(angle) };
    };

    const targetConfigs = targets.map((bg) => {
        const depth = parseFloat(bg.dataset.motionDepth || '1');
        const scale = parseFloat(bg.dataset.motionScale || '1.08');
        const { x: dirX, y: dirY } = randomVector();
        return { bg, depth, scale, dirX, dirY };
    });

    document.addEventListener('mousemove', (e) => {
        const width = window.innerWidth;
        const height = window.innerHeight;
        const normX = (e.clientX - width / 2) / (width / 2);
        const normY = (e.clientY - height / 2) / (height / 2);
        const moveX = signedSquare(normX) * moveStrength;
        const moveY = signedSquare(normY) * moveStrength;

        targetConfigs.forEach((c) => {
            const offsetX = moveX * c.dirX;
            const offsetY = moveY * c.dirY;
            c.bg.style.transform =
                `translate3d(${-offsetX * c.depth}px, ${-offsetY * c.depth}px, 0) scale(${c.scale})`;
        });
    });
})();

/* Subtle scroll-reveal for cards — uses a CSS animation so it does not
   touch inline `transition` and therefore does not override the hover
   transitions on transform/box-shadow defined in site.css. */
(() => {
    if (!('IntersectionObserver' in window)) return;
    const items = document.querySelectorAll('.kd-card, .kd-pair, .kd-side-card, .kd-mason-item');
    if (!items.length) return;

    items.forEach((el) => el.classList.add('kd-reveal-init'));

    const io = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add('kd-reveal-in');
                io.unobserve(entry.target);
            }
        });
    }, { threshold: 0.12 });

    items.forEach((el) => io.observe(el));
})();
