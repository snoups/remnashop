import { ExternalLink, Pause, Play, X } from "lucide-react";
import { AnimatePresence, motion, type Variants } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";

import { localized } from "@entities/announcements/api";
import type { Announcement } from "@entities/announcements/api";
import { BrandLogo } from "@shared/ui/BrandLogo";
import { GLASS_SOLID_LINK_BUTTON_CLASS } from "@shared/ui/classes";
import { StatusPill } from "@shared/ui/glass/StatusPill";
import { IconButton } from "@shared/ui/IconButton";

const SLIDE_MS = 6000;
const EASE_OUT: [number, number, number, number] = [0.2, 0.8, 0.2, 1];

interface Move {
  /** 1: forward, -1: back */
  direction: number;
  /** a whole story changes, not a slide inside one */
  isStory: boolean;
}

// a slide inside a story nudges over and fades; a new story pushes the old one out of the card
const offset = ({ direction, isStory }: Move) => direction * (isStory ? 100 : 8);
const SLIDE_VARIANTS: Variants = {
  enter: (move: Move) => ({ x: `${offset(move)}%`, opacity: move.isStory ? 1 : 0 }),
  shown: { x: "0%", opacity: 1, transition: { duration: 0.35, ease: EASE_OUT } },
  leave: (move: Move) => ({ x: `${-offset(move)}%`, opacity: 0, transition: { duration: 0.35, ease: EASE_OUT } }),
};

interface AnnouncementsCarouselProps {
  /** stories with at least one slide, newest first */
  stories: Announcement[];
  startIndex: number;
  /** fires for every story the viewer lands on */
  onView?: (id: string) => void;
  onClose: () => void;
}

export function AnnouncementsCarousel({ stories, startIndex, onView, onClose }: AnnouncementsCarouselProps) {
  const { t, i18n } = useTranslation();
  const [storyIndex, setStoryIndex] = useState(startIndex);
  const [slideIndex, setSlideIndex] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [paused, setPaused] = useState(false);
  const [move, setMove] = useState<Move>({ direction: 1, isStory: false });
  const rootRef = useRef<HTMLDivElement>(null);

  const story = stories[storyIndex];
  const slide = story?.slides[slideIndex];
  const isCritical = story?.severity === "critical";

  const goToStory = useCallback(
    (index: number) => {
      if (index < 0 || index >= stories.length) return;
      setMove({ direction: index > storyIndex ? 1 : -1, isStory: true });
      setStoryIndex(index);
      setSlideIndex(0);
      setElapsed(0);
    },
    [stories.length, storyIndex],
  );

  const next = useCallback(() => {
    if (!story) return;
    if (slideIndex < story.slides.length - 1) {
      setMove({ direction: 1, isStory: false });
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
      setMove({ direction: -1, isStory: false });
      setSlideIndex(slideIndex - 1);
      setElapsed(0);
    } else {
      goToStory(storyIndex - 1);
    }
  }, [slideIndex, storyIndex, goToStory]);

  // a ref, so a new callback identity each render doesn't re-report the same story
  const onViewRef = useRef(onView);
  onViewRef.current = onView;
  const storyId = story?.id;
  useEffect(() => {
    if (storyId) onViewRef.current?.(storyId);
  }, [storyId]);

  // a story switch can unmount or disable the clicked control, which drops focus to <body>
  useEffect(() => {
    rootRef.current?.focus();
  }, [storyIndex]);

  // per frame, so the progress bar moves smoothly; capped so a held last slide stops re-rendering
  useEffect(() => {
    if (paused) return;
    let frame = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const delta = now - last;
      last = now;
      setElapsed((value) => Math.min(SLIDE_MS, value + delta));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
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
      <motion.button
        key={neighbour.id}
        type="button"
        onClick={() => goToStory(index)}
        initial={{ opacity: 0 }}
        animate={{ opacity: 0.4 }}
        whileHover={{ opacity: 0.7 }}
        transition={{ duration: 0.25, ease: "easeOut" }}
        className="glass-panel relative hidden aspect-[9/16] w-52 shrink-0 overflow-hidden rounded-3xl text-left lg:block"
      >
        {neighbour.slides[0]?.image_url && (
          <img src={neighbour.slides[0].image_url} alt="" className="absolute inset-0 size-full object-cover" />
        )}
        <span className="absolute inset-x-4 bottom-4 text-[13px] font-medium text-foreground">
          {localized(neighbour.title, i18n.language)}
        </span>
      </motion.button>
    );
  };

  // straight to <body>, not DialogPortal: shorts cover the whole viewport, like the donate dialog
  return createPortal(
      <div
        ref={rootRef}
        tabIndex={-1}
        onKeyDown={onKeyDown}
        className="fixed inset-0 z-50 flex items-center justify-center gap-10 bg-black/55 outline-none backdrop-blur-3xl"
      >
        <div className="absolute left-6 top-5 hidden items-center gap-3 sm:flex">
          <BrandLogo className="size-9 text-primary" />
          <span className="flex flex-col">
            <span className="text-[15px] font-semibold tracking-tight text-foreground">{t("announcements.heading")}</span>
            <span className="text-[12px] text-muted-foreground">
              {t("announcements.counter", { current: storyIndex + 1, total: stories.length })}
            </span>
          </span>
        </div>

        {side(storyIndex - 1)}

        <div className="glass-dialog relative h-dvh w-full overflow-hidden sm:aspect-[9/16] sm:h-[min(720px,90vh)] sm:w-auto sm:rounded-3xl">
          <button type="button" onClick={prev} className="absolute inset-y-0 left-0 w-1/3" />
          <button type="button" onClick={next} className="absolute inset-y-0 right-0 w-2/3" />

          {/* a sibling over the tap zones: clicks pass through to them, only the link catches its own */}
          <AnimatePresence initial={false} custom={move}>
            <motion.div
              key={`${story.id}:${slideIndex}`}
              custom={move}
              variants={SLIDE_VARIANTS}
              initial="enter"
              animate="shown"
              exit="leave"
              className="pointer-events-none absolute inset-0"
            >
              {slide.image_url ? (
                <img src={slide.image_url} alt="" className="absolute inset-0 size-full object-cover" />
              ) : (
                <div className={`absolute inset-0 ${isCritical ? "bg-warning/15" : "bg-primary/10"}`} />
              )}
              {/* keeps the text readable over a photo; a plain tint doesn't need it */}
              {slide.image_url && <div className="absolute inset-x-0 bottom-0 h-3/5 bg-gradient-to-t from-black/95 to-transparent" />}
              <div className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-col gap-2 p-4">
                <span className="text-[21px] font-bold leading-tight tracking-tight text-foreground">{title}</span>
                <span className="whitespace-pre-line text-[13px] leading-relaxed text-foreground/90">
                  {localized(slide.text, i18n.language)}
                </span>
                {slide.url && (
                  <a
                    href={slide.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`pointer-events-auto mt-2 ${GLASS_SOLID_LINK_BUTTON_CLASS}`}
                  >
                    {localized(slide.url_label, i18n.language) || t("announcements.openLink")}
                    <ExternalLink className="size-4" />
                  </a>
                )}
              </div>
            </motion.div>
          </AnimatePresence>

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
                <StatusPill tone="warning">{t("announcements.critical")}</StatusPill>
              )}
              <span className="flex-1" />
              <IconButton
                size="9"
                tone="panel"
                className="pointer-events-auto"
                onClick={() => setPaused(!paused)}
              >
                {paused ? <Play className="size-4 text-white" /> : <Pause className="size-4 text-white" />}
              </IconButton>
            </div>
          </div>

        </div>

        {side(storyIndex + 1)}

        <IconButton
          size="9"
          tone="panel"
          className="absolute right-4 top-4 z-10"
          onClick={onClose}
        >
          <X className="size-4 text-white" />
        </IconButton>
      </div>,
    document.body,
  );
}
