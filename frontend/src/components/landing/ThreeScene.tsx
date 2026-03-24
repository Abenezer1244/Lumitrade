"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

interface ThreeSceneProps {
  visible: boolean;
}

export default function ThreeScene({ visible }: ThreeSceneProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<{
    renderer: THREE.WebGLRenderer;
    scene: THREE.Scene;
    camera: THREE.PerspectiveCamera;
    frameId: number;
    orbitSpheres: THREE.Mesh[];
    centralMesh: THREE.Mesh;
    particles: THREE.Points;
    lines: THREE.LineSegments;
    scrollProgress: { value: number };
    ctaProgress: { value: number };
  } | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const container = containerRef.current;
    const width = window.innerWidth;
    const height = window.innerHeight;

    // Scene
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x0d1b2a, 0.0008);

    // Camera
    const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 2000);
    camera.position.set(0, 0, 8);

    // Renderer
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x0d1b2a, 1);
    container.appendChild(renderer.domElement);

    // Lighting
    const ambientLight = new THREE.AmbientLight(0x1a2a4a, 0.6);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0x3d5a8c, 0.8);
    directionalLight.position.set(5, 5, 5);
    scene.add(directionalLight);

    const pointLight = new THREE.PointLight(0x00c896, 0.6, 30);
    pointLight.position.set(0, 0, 3);
    scene.add(pointLight);

    // Central icosahedron (wireframe, emerald-tinted) — LARGE to fill viewport
    const icoGeometry = new THREE.IcosahedronGeometry(3.5, 2);
    const icoMaterial = new THREE.MeshPhongMaterial({
      color: 0x00c896,
      wireframe: true,
      transparent: true,
      opacity: 0.18,
      emissive: 0x00c896,
      emissiveIntensity: 0.15,
    });
    const centralMesh = new THREE.Mesh(icoGeometry, icoMaterial);
    scene.add(centralMesh);

    // Inner solid icosahedron (subtle glow core)
    const innerGeo = new THREE.IcosahedronGeometry(1.8, 2);
    const innerMat = new THREE.MeshPhongMaterial({
      color: 0x00e89d,
      transparent: true,
      opacity: 0.05,
      emissive: 0x00e89d,
      emissiveIntensity: 0.15,
    });
    const innerMesh = new THREE.Mesh(innerGeo, innerMat);
    scene.add(innerMesh);

    // Orbiting spheres
    const orbitSpheres: THREE.Mesh[] = [];
    const orbitColors = [0x3d8eff, 0x00e89d, 0x00c4ff, 0xffb347, 0x8b5cf6];
    const orbitRadii = [5.0, 6.0, 7.0, 5.5, 6.5];

    for (let i = 0; i < 5; i++) {
      const sphereGeo = new THREE.SphereGeometry(0.12, 16, 16);
      const sphereMat = new THREE.MeshPhongMaterial({
        color: orbitColors[i],
        emissive: orbitColors[i],
        emissiveIntensity: 0.5,
        transparent: true,
        opacity: 0.8,
      });
      const sphere = new THREE.Mesh(sphereGeo, sphereMat);
      scene.add(sphere);
      orbitSpheres.push(sphere);

      // Glow around each sphere
      const glowGeo = new THREE.SphereGeometry(0.3, 16, 16);
      const glowMat = new THREE.MeshBasicMaterial({
        color: orbitColors[i],
        transparent: true,
        opacity: 0.1,
      });
      const glow = new THREE.Mesh(glowGeo, glowMat);
      sphere.add(glow);
    }

    // Connection lines (dynamic, updated per frame)
    const lineGeometry = new THREE.BufferGeometry();
    const linePositions = new Float32Array(5 * 2 * 3); // 5 lines, 2 points each, 3 coords
    lineGeometry.setAttribute("position", new THREE.BufferAttribute(linePositions, 3));
    const lineMaterial = new THREE.LineBasicMaterial({
      color: 0x00c896,
      transparent: true,
      opacity: 0.15,
    });
    const lines = new THREE.LineSegments(lineGeometry, lineMaterial);
    scene.add(lines);

    // Particle field (background stars)
    const particleCount = 2000;
    const particleGeometry = new THREE.BufferGeometry();
    const particlePositions = new Float32Array(particleCount * 3);
    const particleSizes = new Float32Array(particleCount);

    for (let i = 0; i < particleCount; i++) {
      particlePositions[i * 3] = (Math.random() - 0.5) * 60;
      particlePositions[i * 3 + 1] = (Math.random() - 0.5) * 60;
      particlePositions[i * 3 + 2] = (Math.random() - 0.5) * 60;
      particleSizes[i] = Math.random() * 2 + 0.5;
    }

    particleGeometry.setAttribute("position", new THREE.BufferAttribute(particlePositions, 3));
    particleGeometry.setAttribute("size", new THREE.BufferAttribute(particleSizes, 1));

    const particleMaterial = new THREE.PointsMaterial({
      color: 0x6a8ebd,
      size: 0.05,
      transparent: true,
      opacity: 0.7,
      sizeAttenuation: true,
    });
    const particles = new THREE.Points(particleGeometry, particleMaterial);
    scene.add(particles);

    // Scroll progress tracker
    const scrollProgress = { value: 0 };
    const ctaProgress = { value: 0 };

    // GSAP ScrollTrigger for hero scroll
    const heroTrigger = ScrollTrigger.create({
      trigger: "#hero-spacer",
      start: "top top",
      end: "bottom top",
      scrub: 1,
      onUpdate: (self) => {
        scrollProgress.value = self.progress;
      },
    });

    // GSAP ScrollTrigger for CTA section (scene returns)
    const ctaTrigger = ScrollTrigger.create({
      trigger: "#cta-section",
      start: "top bottom",
      end: "bottom bottom",
      scrub: 1,
      onUpdate: (self) => {
        ctaProgress.value = self.progress;
      },
    });

    // Store references
    sceneRef.current = {
      renderer,
      scene,
      camera,
      frameId: 0,
      orbitSpheres,
      centralMesh,
      particles,
      lines,
      scrollProgress,
      ctaProgress,
    };

    // Animation loop
    const clock = new THREE.Clock();

    const animate = () => {
      const ref = sceneRef.current;
      if (!ref) return;

      const elapsed = clock.getElapsedTime();
      const sp = ref.scrollProgress.value;
      const cta = ref.ctaProgress.value;

      // Base rotation + scroll-accelerated rotation
      const rotSpeed = 0.15 + sp * 0.6;
      ref.centralMesh.rotation.x = elapsed * rotSpeed * 0.3;
      ref.centralMesh.rotation.y = elapsed * rotSpeed * 0.5;
      innerMesh.rotation.x = -elapsed * 0.1;
      innerMesh.rotation.y = elapsed * 0.15;

      // Camera zoom on scroll
      const baseZ = 8;
      const scrollZ = baseZ - sp * 3;
      ref.camera.position.z = scrollZ;

      // Orbit spheres
      const positions = ref.lines.geometry.attributes.position as THREE.BufferAttribute;
      for (let i = 0; i < ref.orbitSpheres.length; i++) {
        const angle = elapsed * (0.2 + i * 0.08) + (i * Math.PI * 2) / 5;
        const r = orbitRadii[i];
        const tiltAngle = (i * Math.PI) / 5;

        ref.orbitSpheres[i].position.x = Math.cos(angle) * r;
        ref.orbitSpheres[i].position.y = Math.sin(angle) * r * Math.cos(tiltAngle) * 0.6;
        ref.orbitSpheres[i].position.z = Math.sin(angle) * r * Math.sin(tiltAngle) * 0.4;

        // Update line from center to sphere
        positions.array[i * 6] = 0;
        positions.array[i * 6 + 1] = 0;
        positions.array[i * 6 + 2] = 0;
        positions.array[i * 6 + 3] = ref.orbitSpheres[i].position.x;
        positions.array[i * 6 + 4] = ref.orbitSpheres[i].position.y;
        positions.array[i * 6 + 5] = ref.orbitSpheres[i].position.z;
      }
      positions.needsUpdate = true;

      // Particles slow rotation
      ref.particles.rotation.y = elapsed * 0.01;
      ref.particles.rotation.x = elapsed * 0.005;

      // Scene opacity based on scroll (fade out during content, fade back for CTA)
      const heroOpacity = 1 - sp;
      const ctaOpacity = cta;
      const finalOpacity = Math.max(heroOpacity, ctaOpacity);
      renderer.domElement.style.opacity = String(Math.max(0, finalOpacity));

      ref.renderer.render(ref.scene, ref.camera);
      ref.frameId = requestAnimationFrame(animate);
    };

    animate();

    // Handle resize
    const handleResize = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", handleResize);

    // Cleanup
    return () => {
      window.removeEventListener("resize", handleResize);
      heroTrigger.kill();
      ctaTrigger.kill();

      if (sceneRef.current) {
        cancelAnimationFrame(sceneRef.current.frameId);
      }

      // Dispose all geometries and materials
      scene.traverse((obj) => {
        if (obj instanceof THREE.Mesh || obj instanceof THREE.Points || obj instanceof THREE.LineSegments) {
          obj.geometry.dispose();
          if (Array.isArray(obj.material)) {
            obj.material.forEach((m) => m.dispose());
          } else {
            obj.material.dispose();
          }
        }
      });

      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }

      sceneRef.current = null;
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="fixed inset-0 z-0"
      style={{
        opacity: visible ? 1 : 0,
        transition: "opacity 0.8s ease",
        pointerEvents: "none",
      }}
    />
  );
}
