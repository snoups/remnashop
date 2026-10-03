import { ChevronLeft, ChevronRight, ExternalLink, Pause, Play, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";

import { localized } from "@entities/announcements/api";
import type { Announcement } from "@entities/announcements/api";
import { DialogPortal } from "@shared/ui/DialogPortal";
import { IconButton } from "@shared/ui/IconButton";

const SLIDE_MS = 6000;
const TICK_MS = 100;

interface AnnouncementsCarouselProps {
  /** stories with at least one slide, newest first */
  stories: Announcement[];
  startIndex: number;
  onClose: () => void;
}

export function AnnouncementsCarousel({ stories, startIndex, onClose }: AnnouncementsCarouselProps) {
  const { t, i18n } = useTranslation();
  const [storyIndex, setStoryIndex] = useState(startIndex);
  const [slideIndex, setSlideIndex] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [paused, setPaused] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const story = stories[storyIndex];
  const slide = story?.slides[slideIndex];
  const isCritical = story?.severity === "critical";

  const goToStory = useCallback(
    (index: number) => {
      if (index < 0 || index >= stories.length) return;
      setStoryIndex(index);
      setSlideIndex(0);
      setElapsed(0);
    },
    [stories.length],
  );

  const next = useCallback(() => {
    if (!story) return;
    if (slideIndex < story.slides.length - 1) {
      setSlideIndex(slideIndex + 1);
      setElapsed(0);
    } else if (storyIndex < stories.length - 1) {
      goToStory(storyIndex + 1);
    } else {
      setElapsed(SLIDE_MS);
    }
  }, [story, slideIndex, storyIndex, stories.length, goToStory]);

  const prev = useCallback(() => {
    if (slideIndex > 0) {
      setSlideIndex(slideIndex - 1);
      setElapsed(0);
    } else {
      goToStory(storyIndex - 1);
    }
  }, [slideIndex, storyIndex, goToStory]);

  // a story switch can unmount or disable the clicked control, which drops focus to <body>
  useEffect(() => {
    rootRef.current?.focus();
  }, [storyIndex]);

  useEffect(() => {
    if (paused) return;
    const timer = setInterval(() => setElapsed((value) => value + TICK_MS), TICK_MS);
    return () => clearInterval(timer);
  }, [paused]);

  // the last slide of the last story holds at full progress instead of looping
  const atEnd = !!story && storyIndex === stories.length - 1 && slideIndex === story.slides.length - 1;
  useEffect(() => {
    if (elapsed >= SLIDE_MS && !atEnd) next();
  }, [elapsed, atEnd, next]);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") onClose();
    else if (event.key === "ArrowRight") next();
    else if (event.key === "ArrowLeft") prev();
  };

  if (!story || !slide) return null;

  const title = localized(story.title, i18n.language);

  const side = (index: number) => {
    const neighbour = stories[index];
    if (!neighbour) return <div className="hidden w-52 shrink-0 lg:block" />;
    return (
      <button
        type="button"
        onClick={() => goToStory(index)}
        aria-label={t(index < storyIndex ? "announcements.prevStory" : "announcements.nextStory")}
        className="relative hidden aspect-[9/16] w-52 shrink-0 overflow-hidden rounded-2xl bg-surface/40 text-left opacity-40 transition-opacity hover:opacity-70 lg:block"
      >
        {neighbour.slides[0]?.image_url && (
          <img src={neighbour.slides[0].image_url} alt="" className="absolute inset-0 size-full object-cover" />
        )}
        <span className="absolute inset-x-3 bottom-3 text-[13px] font-semibold text-foreground">
          {localized(neighbour.title, i18n.language)}
        </span>
      </button>
    );
  };

  return (
    <DialogPortal>
      <div
        ref={rootRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onKeyDown={onKeyDown}
        className="fixed inset-0 z-50 flex items-center justify-center gap-10 bg-black/85 outline-none"
      >
        <div className="absolute left-6 top-5 hidden items-center gap-3 sm:flex">
          <span className="flex size-9 items-center justify-center rounded-full bg-primary text-[13px] font-extrabold text-primary-foreground">
            rs
          </span>
          <span className="flex flex-col">
            <span className="text-[15px] font-bold text-foreground">{t("announcements.from")}</span>
            <span className="text-[12.5px] text-muted-foreground">
              {t("announcements.counter", { current: storyIndex + 1, total: stories.length })}
            </span>
          </span>
        </div>

        {side(storyIndex - 1)}

        <div className="relative h-dvh w-full overflow-hidden bg-surface sm:aspect-[9/16] sm:h-[min(720px,90vh)] sm:w-auto sm:rounded-dialog sm:border sm:border-glass-border">
          {slide.image_url ? (
            <img src={slide.image_url} alt="" className="absolute inset-0 size-full object-cover" />
          ) : (
            <div className={`absolute inset-0 ${isCritical ? "bg-warning/15" : "bg-accent"}`} />
          )}
          <div className="absolute inset-x-0 bottom-0 h-3/5 bg-gradient-to-t from-black/95 to-transparent" />

          <button type="button" aria-label={t("announcements.prevSlide")} onClick={prev} className="absolute inset-y-0 left-0 w-1/3" />
          <button type="button" aria-label={t("announcements.nextSlide")} onClick={next} className="absolute inset-y-0 right-0 w-2/3" />

          <div className="pointer-events-none absolute inset-x-0 top-0 flex flex-col gap-3 p-3">
            <div className="flex gap-1">
              {story.slides.map((_, index) => (
                <span key={index} className="h-[3px] flex-1 overflow-hidden rounded-full bg-white/25">
                  <span
                    className="block h-full rounded-full bg-foreground"
                    style={{
                      width: `${index < slideIndex ? 100 : index === slideIndex ? Math.min(100, (elapsed / SLIDE_MS) * 100) : 0}%`,
                    }}
                  />
                </span>
              ))}
            </div>
            <div className="flex items-center gap-2">
              {isCritical && (
                <span className="rounded-full bg-warning/20 px-2.5 py-0.5 text-[11.5px] font-semibold text-warning">
                  {t("announcements.critical")}
                </span>
              )}
              <span className="flex-1" />
              <IconButton
                size="9"
                tone="glass"
                className="pointer-events-auto"
                onClick={() => setPaused(!paused)}
                aria-label={t(paused ? "announcements.play" : "announcements.pause")}
              >
                {paused ? <Play className="size-4" /> : <Pause className="size-4" />}
              </IconButton>
              <IconButton
                size="9"
                tone="glass"
                className="pointer-events-auto"
                onClick={onClose}
                aria-label={t("announcements.close")}
              >
                <X className="size-4" />
              </IconButton>
            </div>
          </div>

          <div className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-col gap-2.5 p-6">
            <span className="text-[22px] font-bold leading-tight text-foreground">{title}</span>
            <span className="whitespace-pre-line text-[14.5px] leading-relaxed text-foreground/80">
              {localized(slide.text, i18n.language)}
            </span>
            {slide.url && (
              <a
                href={slide.url}
                target="_blank"
                rel="noopener noreferrer"
                className="pointer-events-auto mt-2 flex h-11 items-center justify-center gap-2 rounded-full bg-primary text-[14px] font-semibold text-primary-foreground"
              >
                {t("announcements.openLink")}
                <ExternalLink className="size-4" />
              </a>
            )}
          </div>
        </div>

        {side(storyIndex + 1)}

        <div className="absolute right-6 top-1/2 hidden -translate-y-1/2 flex-col gap-3 lg:flex">
          <IconButton
            size="9.5"
            tone="glass"
            onClick={() => goToStory(storyIndex - 1)}
            disabled={storyIndex === 0}
            aria-label={t("announcements.prevStory")}
          >
            <ChevronLeft className="size-5" />
          </IconButton>
          <IconButton
            size="9.5"
            tone="glass"
            onClick={() => goToStory(storyIndex + 1)}
            disabled={storyIndex === stories.length - 1}
            aria-label={t("announcements.nextStory")}
          >
            <ChevronRight className="size-5" />
          </IconButton>
        </div>
      </div>
    </DialogPortal>
  );
}
