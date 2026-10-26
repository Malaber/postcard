import SwiftUI

struct ViewersView: View {
    @Bindable var model: AppModel
    @State private var newName = ""
    @FocusState private var nameFocused: Bool
    var body: some View {
        NavigationStack {
            List {
                Section {
                    TextField("Viewer name", text: $newName).accessibilityIdentifier("newViewerName")
                        .focused($nameFocused).submitLabel(.done).onSubmit { nameFocused = false }
                    Button("Create viewer", systemImage: "plus") {
                        nameFocused = false
                        Task { await model.run {
                            try await model.api?.mutate("frames/", values: ["name": newName])
                            try await model.refresh(); newName = ""
                        } }
                    }.disabled(newName.trimmingCharacters(in: .whitespaces).isEmpty || model.busy)
                } header: { Text("A home for your photos") }
                footer: { Text("Create a viewer for each screen. Open its private link on a tablet, TV or browser to start the slideshow.") }
                Section("Your viewers") {
                    ForEach(model.viewers) { viewer in
                        NavigationLink(value: viewer.id) {
                            Label { VStack(alignment: .leading) {
                                Text(viewer.name).font(.headline)
                                Text("\(viewer.photos.filter(\.isActive).count) photos showing").font(.caption).foregroundStyle(.secondary)
                            } } icon: { Image(systemName: "display").foregroundStyle(.blue) }
                        }
                    }
                }
            }.navigationTitle("Viewers")
            .navigationDestination(for: String.self) { id in ViewerEditor(model: model, viewerID: id) }
            .refreshable { await model.run { try await model.refresh() } }
        }
    }
}

struct ViewerEditor: View {
    @Bindable var model: AppModel
    let viewerID: String
    @State private var name = ""
    @State private var confirmDelete = false
    @State private var confirmRotate = false
    @Environment(\.dismiss) private var dismiss
    var viewer: Viewer? { model.viewers.first { $0.id == viewerID } }
    var body: some View {
        Form {
            Section("Viewer name") {
                TextField("Name", text: $name).accessibilityIdentifier("editViewerName")
                Button("Save name") {
                    Task { await model.run {
                        try await model.api?.mutate("frames/\(viewerID)/", method: "PATCH", values: ["name": name])
                        try await model.refresh()
                    } }
                }.disabled(name.trimmingCharacters(in: .whitespaces).isEmpty || model.busy)
            }
            if let viewer {
                Section {
                    ShareLink(item: viewer.viewerUrl) { Label("Share viewer link", systemImage: "square.and.arrow.up") }
                    Link("Open viewer", destination: viewer.viewerUrl)
                    Button("Replace private link") { confirmRotate = true }
                } header: { Text("Connect your screen") }
                footer: { Text("Anyone with this link can see this viewer’s photos. Replacing it disconnects screens using the old link; already downloaded photos cannot be recalled.") }
                Section {
                    Button("Delete viewer", role: .destructive) { confirmDelete = true }
                } footer: { Text("Deletes this viewer and all its photos.") }
            }
        }.navigationTitle(viewer?.name ?? "Viewer").onAppear { name = viewer?.name ?? "" }
        .disabled(model.busy)
        .confirmationDialog("Disconnect existing screens?", isPresented: $confirmRotate, titleVisibility: .visible) {
            Button("Replace link", role: .destructive) { Task { await model.run {
                try await model.api?.mutate("frames/\(viewerID)/rotate/"); try await model.refresh()
            } } }
        }
        .confirmationDialog("Delete viewer and all its photos?", isPresented: $confirmDelete, titleVisibility: .visible) {
            Button("Delete permanently", role: .destructive) { Task { await model.run {
                try await model.api?.mutate("frames/\(viewerID)/", method: "DELETE")
                try await model.refresh(); dismiss()
            } } }
        }
    }
}

struct PhotoEditor: View {
    @Bindable var model: AppModel
    let photo: Photo
    @State private var caption = ""
    @State private var active = true
    @State private var viewerID = ""
    @State private var confirmDelete = false
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            Form {
                TextField("Caption", text: $caption).accessibilityIdentifier("editCaption")
                Toggle("Show on viewer", isOn: $active)
                Picker("Assigned viewer", selection: $viewerID) {
                    ForEach(model.viewers) { Text($0.name).tag($0.id) }
                }
                Button("Delete photo", role: .destructive) { confirmDelete = true }
            }.navigationTitle("This moment")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { Task { await model.run {
                        try await model.api?.mutate("photos/\(photo.id)/", method: "PATCH",
                            values: ["caption": caption, "is_active": active, "frame_id": viewerID])
                        try await model.refresh(); dismiss()
                    } } }.disabled(model.busy || caption.count > 255)
                }
            }.onAppear {
                caption = photo.caption; active = photo.isActive
                viewerID = model.viewers.first { $0.photos.contains(where: { $0.id == photo.id }) }?.id ?? ""
            }
            .confirmationDialog("Delete this photo?", isPresented: $confirmDelete, titleVisibility: .visible) {
                Button("Delete permanently", role: .destructive) { Task { await model.run {
                    try await model.api?.mutate("photos/\(photo.id)/", method: "DELETE")
                    try await model.refresh(); dismiss()
                } } }
            }
        }
    }
}
