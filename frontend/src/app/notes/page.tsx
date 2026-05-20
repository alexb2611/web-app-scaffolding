"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

import { useAuth } from "@/lib/auth";
import { ApiError, client, unwrap } from "@/lib/api";
import { noteCreateSchema, type NoteCreateInput } from "@/lib/note-schemas";
import type { components } from "@/lib/api-types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";

type Note = components["schemas"]["NoteResponse"];

export default function NotesPage() {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const [notes, setNotes] = useState<Note[]>([]);
  const [apiError, setApiError] = useState("");

  const form = useForm<NoteCreateInput>({
    resolver: zodResolver(noteCreateSchema),
    mode: "onTouched",
    defaultValues: { title: "", body: "" },
  });

  // Auth-gate — same pattern as the dashboard page. Middleware also
  // redirects, but the effect handles the case where the session
  // expires while the tab is open.
  useEffect(() => {
    if (!isLoading && !user) router.push("/login");
  }, [isLoading, user, router]);

  // Load existing notes once authenticated. `useCallback` so we can
  // call it from the submit handler to refresh after a mutation if we
  // ever want to switch from optimistic updates.
  const refresh = useCallback(async (): Promise<void> => {
    try {
      const data = await unwrap(client.GET("/api/v1/notes"));
      setNotes(data);
    } catch (err) {
      setApiError(err instanceof ApiError ? err.detail : "Failed to load notes");
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    void refresh();
  }, [user, refresh]);

  async function onSubmit(values: NoteCreateInput): Promise<void> {
    setApiError("");
    try {
      const created = await unwrap(client.POST("/api/v1/notes", { body: values }));
      // Optimistic prepend — matches the server's newest-first ordering.
      setNotes([created, ...notes]);
      form.reset();
    } catch (err) {
      setApiError(err instanceof ApiError ? err.detail : "Something went wrong");
    }
  }

  async function handleDelete(noteId: string): Promise<void> {
    setApiError("");
    try {
      await unwrap(
        client.DELETE("/api/v1/notes/{note_id}", {
          params: { path: { note_id: noteId } },
        }),
      );
      setNotes(notes.filter((n) => n.id !== noteId));
    } catch (err) {
      setApiError(err instanceof ApiError ? err.detail : "Failed to delete note");
    }
  }

  if (isLoading || !user) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Loading…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl p-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Notes</h1>
        <Link
          href="/dashboard"
          className="text-primary text-sm underline underline-offset-4 hover:opacity-80"
        >
          ← Dashboard
        </Link>
      </div>

      {apiError && (
        <div
          role="alert"
          className="bg-destructive/10 text-destructive mt-4 rounded-md px-4 py-3 text-sm"
        >
          {apiError}
        </div>
      )}

      <Card className="mt-8">
        <CardHeader>
          <CardTitle>New note</CardTitle>
          <CardDescription>Add a quick note to your list.</CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(onSubmit)}
              noValidate
              className="space-y-4"
            >
              <FormField
                control={form.control}
                name="title"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Title</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="A short summary"
                        autoComplete="off"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="body"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Body</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="What do you want to remember?"
                        autoComplete="off"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting ? "Adding…" : "Add note"}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>

      <section className="mt-8 space-y-3">
        {notes.length === 0 ? (
          <p className="text-muted-foreground text-sm">No notes yet.</p>
        ) : (
          notes.map((note) => (
            <Card key={note.id}>
              <CardContent className="flex items-start justify-between gap-4 pt-6">
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{note.title}</p>
                  <p className="text-muted-foreground mt-1 text-sm break-words">
                    {note.body}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void handleDelete(note.id)}
                  aria-label={`Delete note: ${note.title}`}
                >
                  Delete
                </Button>
              </CardContent>
            </Card>
          ))
        )}
      </section>
    </main>
  );
}
