import Image from "@tiptap/extension-image";
import { EditorContent, useEditor } from "@tiptap/react";
import type { ChainedCommands, Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import {
  Bold,
  Heading1,
  Heading2,
  Heading3,
  ImagePlus,
  Italic,
  Link,
  List,
  ListOrdered,
  Minus,
  Quote,
  RectangleHorizontal,
  Strikethrough,
  Underline,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ComponentType } from "react";
import { useTranslation } from "react-i18next";

import { BROADCAST_VARIABLES, uploadEmailImage } from "@entities/broadcasts/api";
import { VariablePicker } from "@features/dialog-canvas-editor/VariablePicker";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { Card } from "@shared/ui/Card";
import { IconButton } from "@shared/ui/IconButton";
import { Spinner } from "@shared/ui/Spinner";
import { FIELD_SURFACE_CLASS, TextInput } from "@shared/ui/TextInput";
import { Tooltip } from "@shared/ui/Tooltip";

import { EmailButton } from "@pages/broadcasts/editor/email-button";
import { dropForeignImages, EMAIL_URL_RE, referencedImageIds, toEditorHtml, toStoredHtml, useEmailImageUrls } from "@pages/broadcasts/editor/email-images";
import { sendsTelegram, setEmailHtml, setEmailSubject } from "@pages/broadcasts/editor/form";
import type { EditorForm } from "@pages/broadcasts/editor/form";
import { LocaleTabs } from "@pages/broadcasts/editor/LocaleTabs";
import { UrlPopoverButton } from "@features/dialog-canvas-editor/UrlPopoverButton";

const MAX_SUBJECT_LENGTH = 200;
const IMAGE_ACCEPT = "image/png,image/jpeg,image/gif";
const formatVariable = (name: string) => `{ $${name} }`;

// keeps the uploaded image's id across edits, so the stored HTML can point back at it;
// an image without one (pasted from elsewhere) never enters the document
const EmailImage = Image.extend({
  parseHTML() {
    return [{ tag: "img[data-image-id]" }];
  },
  addAttributes() {
    return {
      ...this.parent?.(),
      imageId: {
        default: null,
        parseHTML: (el) => el.getAttribute("data-image-id"),
        renderHTML: (attrs) => (attrs.imageId ? { "data-image-id": attrs.imageId as string } : {}),
      },
    };
  },
});

const EXTENSIONS = [
  StarterKit.configure({
    heading: { levels: [1, 2, 3] },
    code: false,
    codeBlock: false,
    link: { openOnClick: false, autolink: true, isAllowedUri: (url) => EMAIL_URL_RE.test(url) },
  }),
  EmailImage,
  EmailButton,
];

const ACTIONS: { key: string; icon: ComponentType<{ className?: string }>; run: (c: ChainedCommands) => ChainedCommands }[] = [
  { key: "bold", icon: Bold, run: (c) => c.toggleBold() },
  { key: "italic", icon: Italic, run: (c) => c.toggleItalic() },
  { key: "underline", icon: Underline, run: (c) => c.toggleUnderline() },
  { key: "strike", icon: Strikethrough, run: (c) => c.toggleStrike() },
  { key: "h1", icon: Heading1, run: (c) => c.toggleHeading({ level: 1 }) },
  { key: "h2", icon: Heading2, run: (c) => c.toggleHeading({ level: 2 }) },
  { key: "h3", icon: Heading3, run: (c) => c.toggleHeading({ level: 3 }) },
  { key: "bullet", icon: List, run: (c) => c.toggleBulletList() },
  { key: "ordered", icon: ListOrdered, run: (c) => c.toggleOrderedList() },
  { key: "quote", icon: Quote, run: (c) => c.toggleBlockquote() },
  { key: "divider", icon: Minus, run: (c) => c.setHorizontalRule() },
];

// Tailwind resets headings and lists; the letter's look is applied by the backend
const BODY_CLASS = [
  "min-h-64 w-full px-3.5 py-3 text-sm leading-relaxed text-foreground outline-none",
  "[&_p]:my-1 [&_h1]:my-2 [&_h1]:text-xl [&_h1]:font-semibold [&_h2]:my-2 [&_h2]:text-lg [&_h2]:font-semibold",
  "[&_h3]:my-2 [&_h3]:text-base [&_h3]:font-semibold [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5",
  "[&_blockquote]:border-l-2 [&_blockquote]:border-border [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground",
  "[&_hr]:my-3 [&_hr]:border-border [&_a]:text-primary [&_a]:underline [&_img]:my-2 [&_img]:max-w-full",
  "[&_a[data-button]]:inline-block [&_a[data-button]]:rounded-full [&_a[data-button]]:bg-primary",
  "[&_a[data-button]]:px-4 [&_a[data-button]]:py-1.5 [&_a[data-button]]:text-primary-foreground [&_a[data-button]]:no-underline",
  "[&_.ProseMirror-selectednode]:outline-2 [&_.ProseMirror-selectednode]:outline-primary",
].join(" ");
const EDITOR_PROPS = { attributes: { class: BODY_CLASS } };

function applyLink(editor: Editor, mark: "link" | "button", href: string) {
  const chain = editor.chain().focus();
  // no selection: the address itself becomes the text
  if (editor.state.selection.empty) chain.insertContent({ type: "text", text: href, marks: [{ type: mark, attrs: { href } }] });
  else chain.setMark(mark, { href });
  chain.run();
}

interface EmailBodyProps {
  initialHtml: string;
  urls: Record<number, string>;
  broadcastId: number | null;
  canAddImage: boolean;
  disabled: boolean;
  onImageAdded: (id: number, url: string) => void;
  onChange: (html: string) => void;
}

function EmailBody({ initialHtml, urls, broadcastId, canAddImage, disabled, onImageAdded, onChange }: EmailBodyProps) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const urlsRef = useRef(urls);
  urlsRef.current = urls;
  const editor = useEditor({
    extensions: EXTENSIONS,
    content: toEditorHtml(initialHtml, urls),
    editable: !disabled,
    editorProps: {
      ...EDITOR_PROPS,
      // an image id this broadcast never had would fail the save; urls holds exactly its own
      transformPastedHTML: (html) => dropForeignImages(html, urlsRef.current),
    },
    onUpdate: ({ editor: e }) => onChange(e.isEmpty ? "" : toStoredHtml(e.getHTML())),
  });

  useEffect(() => editor.setEditable(!disabled), [editor, disabled]);

  const upload = async (file: File) => {
    if (broadcastId === null) return;
    setIsUploading(true);
    try {
      const image = await uploadEmailImage(broadcastId, file);
      const url = URL.createObjectURL(file);
      onImageAdded(image.id, url);
      editor
        .chain()
        .focus()
        .insertContent({ type: "image", attrs: { src: url, imageId: String(image.id) } })
        .run();
    } catch (err) {
      toast.error(getErrorMessage(err, t("broadcasts.editor.email.imageError")));
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className={`overflow-hidden rounded-2xl ${FIELD_SURFACE_CLASS}`}>
      <div className="flex flex-wrap items-center gap-0.5 border-b border-border px-2 py-1.5">
        {ACTIONS.map(({ key, icon: Icon, run }) => (
          <IconButton
            key={key}
            size="7"
            disabled={disabled}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => run(editor.chain().focus()).run()}
          >
            <Icon className="size-4" />
          </IconButton>
        ))}
        <span className="mx-1.5 h-4 w-px bg-border" />
        <UrlPopoverButton
          icon={Link}
          pattern={EMAIL_URL_RE}
          disabled={disabled}
          onInsert={(href) => applyLink(editor, "link", href)}
        />
        <UrlPopoverButton
          icon={RectangleHorizontal}
          pattern={EMAIL_URL_RE}
          disabled={disabled}
          onInsert={(href) => applyLink(editor, "button", href)}
        />
        <span className="group relative">
          <input
            ref={inputRef}
            type="file"
            accept={IMAGE_ACCEPT}
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.target.value = "";
              if (file) void upload(file);
            }}
          />
          <IconButton
            size="7"
            disabled={disabled || broadcastId === null || !canAddImage || isUploading}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => inputRef.current?.click()}
          >
            <ImagePlus className="size-4" />
          </IconButton>
          {canAddImage && (
            <Tooltip
              side="top"
              text={t(broadcastId === null ? "broadcasts.editor.email.imageSaveFirst" : "broadcasts.editor.email.imageHint")}
            />
          )}
        </span>
        <span className="mx-1.5 h-4 w-px bg-border" />
        <VariablePicker
          variables={BROADCAST_VARIABLES}
          format={formatVariable}
          onPick={(token) => editor.chain().focus().insertContent(token).run()}
          disabled={disabled}
        />
      </div>
      <EditorContent editor={editor} />
    </div>
  );
}

interface EmailEditorProps {
  form: EditorForm;
  onChange: (form: EditorForm) => void;
  activeLocale: string;
  onLocaleChange: (locale: string) => void;
  botLocales: string[];
  /** null until the broadcast is first saved: images are uploaded to an existing one */
  broadcastId: number | null;
  canAddImage: boolean;
  canViewImages: boolean;
  disabled: boolean;
}

export function EmailEditor({
  form,
  onChange,
  activeLocale,
  onLocaleChange,
  botLocales,
  broadcastId,
  canAddImage,
  canViewImages,
  disabled,
}: EmailEditorProps) {
  const { t } = useTranslation();
  const subjectRef = useRef<HTMLInputElement>(null);
  const imageIds = Object.values(form.email_contents).flatMap((c) => referencedImageIds(c.html));
  const { urls, ready, add } = useEmailImageUrls(canViewImages ? broadcastId : null, imageIds);
  // a locale added while delivery was Telegram-only has no entry until its first edit
  const content = form.email_contents[activeLocale] ?? { subject: "", html: "" };

  const insertIntoSubject = (token: string) => {
    const start = subjectRef.current?.selectionStart ?? content.subject.length;
    const end = subjectRef.current?.selectionEnd ?? start;
    const subject = content.subject.slice(0, start) + token + content.subject.slice(end);
    onChange(setEmailSubject(form, activeLocale, subject.slice(0, MAX_SUBJECT_LENGTH)));
    const caret = Math.min(start + token.length, MAX_SUBJECT_LENGTH);
    // after React writes the new value, which moves the caret to the end
    requestAnimationFrame(() => subjectRef.current?.setSelectionRange(caret, caret));
  };

  return (
    <Card className="flex flex-col gap-3">
      <LocaleTabs
        title={t("broadcasts.editor.email.title")}
        form={form}
        onChange={onChange}
        activeLocale={activeLocale}
        onLocaleChange={onLocaleChange}
        botLocales={botLocales}
        disabled={disabled}
        manageLocales={!sendsTelegram(form)}
      />
      <div className="flex items-center gap-2">
        <TextInput
          ref={subjectRef}
          type="text"
          value={content.subject}
          maxLength={MAX_SUBJECT_LENGTH}
          disabled={disabled}
          placeholder={t("broadcasts.editor.email.subject")}
          onChange={(event) => onChange(setEmailSubject(form, activeLocale, event.target.value))}
          className="min-w-0 flex-1"
        />
        <VariablePicker
          variables={BROADCAST_VARIABLES}
          format={formatVariable}
          onPick={insertIntoSubject}
          disabled={disabled}
        />
      </div>
      {ready ? (
        <EmailBody
          key={activeLocale}
          initialHtml={content.html}
          urls={urls}
          broadcastId={broadcastId}
          canAddImage={canAddImage}
          disabled={disabled}
          onImageAdded={add}
          onChange={(html) => onChange(setEmailHtml(form, activeLocale, html))}
        />
      ) : (
        <Spinner size="card" />
      )}
    </Card>
  );
}
