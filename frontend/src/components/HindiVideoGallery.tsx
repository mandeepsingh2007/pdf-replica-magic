"use client";

import { useRef, useState } from "react";

export type HindiVideoItem = {
  id: string;
  title: string;
  subtitle: string;
  src: string;
};

type Props = {
  videos: HindiVideoItem[];
};

export default function HindiVideoGallery({ videos }: Props) {
  const refs = useRef<Record<string, HTMLVideoElement | null>>({});
  const [activeId, setActiveId] = useState<string | null>(null);

  const activateAndPlay = async (id: string) => {
    setActiveId(id);
    for (const [key, el] of Object.entries(refs.current)) {
      if (!el) continue;
      if (key === id) {
        try {
          await el.play();
        } catch {
          /* ignore rare play() rejection */
        }
      } else {
        el.pause();
      }
    }
  };

  return (
    <div className="hp-video-grid">
      {videos.map((v) => {
        const isActive = activeId === v.id;
        return (
          <article
            key={v.id}
            className={`hp-video-card${isActive ? " is-active" : ""}`}
          >
            <div className="hp-video-frame">
              <video
                ref={(el) => {
                  refs.current[v.id] = el;
                }}
                src={v.src}
                preload="metadata"
                playsInline
                controls={isActive}
                onPlay={() => {
                  setActiveId(v.id);
                  for (const [key, el] of Object.entries(refs.current)) {
                    if (key !== v.id && el && !el.paused) el.pause();
                  }
                }}
              />
              {!isActive && (
                <button
                  type="button"
                  className="hp-video-play"
                  onClick={() => activateAndPlay(v.id)}
                  aria-label={`${v.title} चलाएँ`}
                >
                  ▶
                </button>
              )}
            </div>
            <div className="hp-video-meta">
              <h2>{v.title}</h2>
              <p>{v.subtitle}</p>
              {!isActive && (
                <button
                  type="button"
                  className="hp-btn hp-btn-sky hp-video-start"
                  onClick={() => activateAndPlay(v.id)}
                >
                  चलाएँ (Play)
                </button>
              )}
            </div>
          </article>
        );
      })}
    </div>
  );
}
