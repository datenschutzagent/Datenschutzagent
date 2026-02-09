"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "../ui/dialog";
import { Button } from "../ui/button";
import { ScrollArea } from "../ui/scroll-area";
import { Textarea } from "../ui/textarea";
import {
  getDocumentContent,
  getDocumentDownloadBlob,
  downloadBlob,
  getDocumentComments,
  createDocumentComment,
  updateDocument,
  type ApiDocument,
  type ApiDocumentComment,
} from "../../lib/api";
import { Download, Loader2, MessageSquare, Pencil, X } from "lucide-react";

export interface DocumentViewDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  document: ApiDocument | null;
  /** When false (e.g. viewer role), hide comment form. */
  canEdit?: boolean;
}

export function DocumentViewDialog({
  open,
  onOpenChange,
  document: doc,
  canEdit = true,
}: DocumentViewDialogProps) {
  const [content, setContent] = useState<string | null>(null);
  const [extractionStatus, setExtractionStatus] = useState<"pending" | "processing" | "done" | "failed" | undefined>(undefined);
  const [extractionError, setExtractionError] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [downloadLoading, setDownloadLoading] = useState(false);
  const [comments, setComments] = useState<ApiDocumentComment[]>([]);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [commentText, setCommentText] = useState("");
  const [commentSubmitting, setCommentSubmitting] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [editContent, setEditContent] = useState("");
  const [saveLoading, setSaveLoading] = useState(false);

  const loadComments = useCallback(async () => {
    if (!doc?.id) return;
    setCommentsLoading(true);
    try {
      const list = await getDocumentComments(doc.id);
      setComments(list);
    } finally {
      setCommentsLoading(false);
    }
  }, [doc?.id]);

  const fetchContent = useCallback(async () => {
    if (!doc?.id) return;
    const res = await getDocumentContent(doc.id);
    setContent(res.content ?? "");
    setExtractionStatus(res.extractionStatus);
    setExtractionError(res.extractionError);
    return res;
  }, [doc?.id]);

  useEffect(() => {
    if (!open || !doc) {
      setContent(null);
      setExtractionStatus(undefined);
      setExtractionError(undefined);
      setComments([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetchContent()
      .then(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, doc?.id, fetchContent]);

  // Poll content while extraction is pending or processing
  useEffect(() => {
    if (!open || !doc?.id || loading) return;
    const status = extractionStatus ?? doc.extractionStatus;
    if (status !== "pending" && status !== "processing") return;
    const interval = setInterval(() => {
      fetchContent();
    }, 2500);
    return () => clearInterval(interval);
  }, [open, doc?.id, doc?.extractionStatus, extractionStatus, loading, fetchContent]);

  useEffect(() => {
    if (!open || !doc) return;
    loadComments();
  }, [open, doc?.id, loadComments]);

  async function handleDownload() {
    if (!doc) return;
    setDownloadLoading(true);
    try {
      const blob = await getDocumentDownloadBlob(doc.id);
      downloadBlob(blob, doc.name);
    } finally {
      setDownloadLoading(false);
    }
  }

  async function handleAddComment() {
    if (!doc || !commentText.trim()) return;
    setCommentSubmitting(true);
    try {
      const created = await createDocumentComment(doc.id, commentText.trim());
      setComments((prev) => [...prev, created]);
      setCommentText("");
    } finally {
      setCommentSubmitting(false);
    }
  }

  function startEdit() {
    setEditContent(content ?? "");
    setEditMode(true);
  }

  function cancelEdit() {
    setEditMode(false);
    setEditContent("");
  }

  async function saveEdit() {
    if (!doc) return;
    setSaveLoading(true);
    try {
      await updateDocument(doc.id, { content: editContent });
      setContent(editContent);
      setEditMode(false);
      setEditContent("");
    } finally {
      setSaveLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>{doc?.name ?? "Dokument"}</DialogTitle>
          <DialogDescription>
            Extrahierter Text aus dem Dokument. Sie können die Originaldatei herunterladen.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3 flex-1 min-h-0">
          <div className="flex justify-end flex-wrap gap-2">
            {canEdit && !editMode && (
              <Button variant="outline" size="sm" onClick={startEdit}>
                <Pencil className="size-4" />
                <span className="ml-2">Text bearbeiten</span>
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownload}
              disabled={!doc || downloadLoading}
            >
              {downloadLoading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Download className="size-4" />
              )}
              <span className="ml-2">Originaldatei herunterladen</span>
            </Button>
          </div>
          <ScrollArea className="flex-1 min-h-[200px] rounded-md border bg-slate-50 p-4">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="size-6 animate-spin text-slate-500" />
              </div>
            ) : editMode ? (
              <div className="space-y-2">
                <textarea
                  className="w-full min-h-[200px] rounded border bg-white p-3 font-sans text-sm text-slate-800 resize-y"
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  placeholder="Extrahierter Text…"
                />
                <div className="flex gap-2">
                  <Button size="sm" onClick={saveEdit} disabled={saveLoading}>
                    {saveLoading ? <Loader2 className="size-4 animate-spin" /> : "Speichern"}
                  </Button>
                  <Button size="sm" variant="outline" onClick={cancelEdit} disabled={saveLoading}>
                    <X className="size-4" />
                    Abbrechen
                  </Button>
                </div>
              </div>
            ) : content === null ? null : (extractionStatus ?? doc?.extractionStatus) === "failed" ? (
              <div className="space-y-2">
                <p className="text-amber-700 dark:text-amber-400 font-medium">Extraktion fehlgeschlagen.</p>
                {extractionError ?? doc?.extractionError ? (
                  <p className="text-sm text-slate-600 dark:text-slate-400 whitespace-pre-wrap break-words">
                    {extractionError ?? doc?.extractionError}
                  </p>
                ) : null}
                <p className="text-slate-500 italic">Kein Text extrahiert.</p>
              </div>
            ) : (extractionStatus ?? doc?.extractionStatus) === "pending" ||
              (extractionStatus ?? doc?.extractionStatus) === "processing" ? (
              <div className="flex flex-col items-center justify-center py-8 gap-2">
                <Loader2 className="size-6 animate-spin text-slate-500" />
                <p className="text-slate-600 dark:text-slate-400">Text wird extrahiert… Bitte kurz warten.</p>
              </div>
            ) : content.trim() === "" ? (
              <p className="text-slate-500 italic">Kein Text extrahiert.</p>
            ) : (
              <pre className="whitespace-pre-wrap font-sans text-sm text-slate-800">
                {content}
              </pre>
            )}
          </ScrollArea>
          <div className="border-t pt-3 space-y-2">
            <h4 className="text-sm font-medium flex items-center gap-2">
              <MessageSquare className="size-4" />
              Kommentare ({comments.length})
            </h4>
            {commentsLoading ? (
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Loader2 className="size-4 animate-spin" />
                Kommentare werden geladen…
              </div>
            ) : (
              <ScrollArea className="max-h-[180px] rounded border bg-slate-50 p-2">
                <div className="space-y-2">
                  {comments.length === 0 ? (
                    <p className="text-sm text-slate-500 italic">Noch keine Kommentare.</p>
                  ) : (
                    comments.map((c) => (
                      <div key={c.id} className="text-sm bg-white rounded p-2 border">
                        <div className="flex justify-between text-xs text-slate-500 mb-1">
                          <span>{c.author}</span>
                          <span>{new Date(c.created_at).toLocaleString("de-DE")}</span>
                        </div>
                        <p className="whitespace-pre-wrap">{c.text}</p>
                      </div>
                    ))
                  )}
                </div>
              </ScrollArea>
            )}
            {canEdit && (
              <div className="flex gap-2">
                <Textarea
                  placeholder="Kommentar hinzufügen…"
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  rows={2}
                  className="resize-none"
                />
                <Button
                  size="sm"
                  onClick={handleAddComment}
                  disabled={!commentText.trim() || commentSubmitting}
                >
                  {commentSubmitting ? <Loader2 className="size-4 animate-spin" /> : "Senden"}
                </Button>
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
