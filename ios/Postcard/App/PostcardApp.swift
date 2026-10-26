import PhotosUI
import SwiftUI

@MainActor @Observable
final class AppModel {
    var credential: Credential?
    var viewers: [Viewer] = []
    var selectedID: String?
    var error: String?
    var busy = false
    var progress = ""
    let signIn = BrowserSignIn()
    var api: PostcardAPI? { credential.map { PostcardAPI(server: $0.server, token: $0.token) } }
    var selected: Viewer? { viewers.first { $0.id == selectedID } }

    init() {
        #if DEBUG
        if let token = ProcessInfo.processInfo.environment["POSTCARD_E2E_TOKEN"],
           let raw = ProcessInfo.processInfo.environment["POSTCARD_E2E_SERVER"], let server = URL(string: raw) {
            credential = Credential(server: server, token: token, userID: "e2e")
            return
        }
        #endif
        do { credential = try CredentialStore.read() } catch { self.error = error.localizedDescription }
    }
    func refresh() async throws {
        guard let api else { return }
        viewers = try PostcardAPI.decoder.decode(ViewersResponse.self, from: await api.data("frames/")).frames
        if !viewers.contains(where: { $0.id == selectedID }) { selectedID = viewers.first?.id }
    }
    func run(_ action: () async throws -> Void) async {
        guard !busy else { return }
        busy = true
        defer { busy = false; progress = "" }
        do { try await action() } catch { self.error = error.localizedDescription }
    }
    func authenticate(_ raw: String) async throws {
        guard let url = URL(string: raw.trimmingCharacters(in: .whitespacesAndNewlines)),
              let parts = URLComponents(url: url, resolvingAgainstBaseURL: false),
              parts.host != nil, parts.user == nil, parts.password == nil,
              parts.query == nil, parts.fragment == nil, parts.path.isEmpty || parts.path == "/",
              parts.scheme == "https" || (parts.scheme == "http" && parts.host == "localhost") else {
            throw PostcardError.server("Enter an HTTPS server origin, such as https://postcard.malaber.de.")
        }
        let credential = try await signIn.signIn(server: url)
        try CredentialStore.save(credential)
        self.credential = credential
        try await refresh()
    }
    func logout() async throws {
        var revocationError: Error?
        do { try await api?.mutate("auth/mobile/logout") } catch { revocationError = error }
        try CredentialStore.remove()
        credential = nil; viewers = []; selectedID = nil
        if revocationError != nil {
            self.error = "Signed out on this device. Server revocation could not be confirmed; the server session expires automatically."
        }
    }
}

@main struct PostcardApp: App {
    @State private var model = AppModel()
    var body: some Scene {
        WindowGroup {
            RootView(model: model)
                .tint(Color(red: 0.08, green: 0.39, blue: 0.93))
                .alert("Something needs attention", isPresented: Binding(get: { model.error != nil },
                    set: { if !$0 { model.error = nil } })) {
                    Button("OK") { model.error = nil }
                } message: { Text(model.error ?? "") }
        }
    }
}

struct RootView: View {
    @Bindable var model: AppModel
    @AppStorage("server") private var server = "https://postcard.malaber.de"
    var body: some View {
        Group {
            if model.credential == nil {
                NavigationStack {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 24) {
                            Image(systemName: "rectangle.stack.badge.plus").font(.system(size: 64)).foregroundStyle(.blue)
                            Text("A little closer,\none photo at a time.").font(.largeTitle.bold())
                            Text("Send everyday moments to the people and screens you love.").font(.title3).foregroundStyle(.secondary)
                            TextField("Server URL", text: $server).textContentType(.URL).keyboardType(.URL)
                                .textInputAutocapitalization(.never).autocorrectionDisabled().textFieldStyle(.roundedBorder)
                                .accessibilityIdentifier("serverURL")
                            Button("Continue with passkey", systemImage: "person.badge.key") {
                                Task { await model.run { try await model.authenticate(server) } }
                            }.buttonStyle(.borderedProminent).disabled(model.busy)
                            Text("New here? Create an account on the next screen. Your photos stay on your chosen server.")
                                .font(.footnote).foregroundStyle(.secondary)
                        }.padding(28)
                    }.navigationTitle("Postcard")
                }
            } else {
                TabView {
                    PhotosView(model: model).tabItem { Label("Photos", systemImage: "photo.on.rectangle") }
                    ViewersView(model: model).tabItem { Label("Viewers", systemImage: "display") }
                    NavigationStack {
                        Form {
                            Section("Connected server") { Text(model.credential?.server.absoluteString ?? "") }
                            Section {
                                Link("Manage passkeys", destination: model.credential!.server.appending(path: "auth/passkeys/"))
                                Button("Sign out", role: .destructive) { Task { await model.run { try await model.logout() } } }
                            }
                        }.navigationTitle("Account")
                    }.tabItem { Label("Account", systemImage: "person.crop.circle") }
                }.task { await model.run { try await model.refresh() } }
            }
        }
    }
}

struct PhotosView: View {
    @Bindable var model: AppModel
    @State private var picks: [PhotosPickerItem] = []
    @State private var caption = ""
    @State private var editing: Photo?
    @State private var uploadMessage = ""
    @FocusState private var captionFocused: Bool
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    if model.viewers.isEmpty {
                        ContentUnavailableView("Give your photos a home", systemImage: "display",
                            description: Text("Create a viewer in the Viewers tab, then add your favourite moments here."))
                    } else {
                        Text("SEND A LITTLE JOY").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                        Picker("Send to", selection: $model.selectedID) {
                            ForEach(model.viewers) { viewer in Text(viewer.name).tag(Optional(viewer.id)) }
                        }.pickerStyle(.menu).accessibilityIdentifier("viewerPicker")
                        TextField("Add a message (optional)", text: $caption).textFieldStyle(.roundedBorder)
                            .accessibilityIdentifier("uploadCaption")
                            .focused($captionFocused).submitLabel(.done).onSubmit { captionFocused = false }
                        PhotosPicker(selection: $picks, maxSelectionCount: 20, matching: .images) {
                            Label("Add photos", systemImage: "plus.circle.fill").frame(maxWidth: .infinity).padding(10)
                        }.buttonStyle(.borderedProminent).disabled(model.busy).accessibilityIdentifier("addPhotos")
                        #if DEBUG
                        if ProcessInfo.processInfo.environment["POSTCARD_E2E_TOKEN"] != nil {
                            Button("Upload test photo") {
                                captionFocused = false
                                let image = UIGraphicsImageRenderer(size: CGSize(width: 64, height: 64)).image { ctx in
                                    UIColor.systemOrange.setFill(); ctx.fill(CGRect(x: 0, y: 0, width: 64, height: 64))
                                }
                                Task { await send([image.jpegData(compressionQuality: 0.9)!]) }
                            }
                        }
                        #endif
                        if model.busy { ProgressView(model.progress.isEmpty ? "Working…" : model.progress) }
                        if !uploadMessage.isEmpty { Text(uploadMessage).foregroundStyle(.secondary).accessibilityIdentifier("uploadStatus") }
                        if let viewer = model.selected {
                            Text("On \(viewer.name)").font(.title2.bold())
                            if viewer.photos.isEmpty { Text("Your next memory belongs here.").foregroundStyle(.secondary) }
                            LazyVGrid(columns: [GridItem(.adaptive(minimum: 145), spacing: 14)], spacing: 14) {
                                ForEach(viewer.photos) { photo in
                                    Button { editing = photo } label: {
                                        VStack(alignment: .leading) {
                                            AsyncImage(url: photo.imageUrl) { image in image.resizable().scaledToFill() }
                                                placeholder: { Rectangle().fill(.quaternary).overlay(Image(systemName: "photo")) }
                                                .frame(height: 160).clipped().clipShape(RoundedRectangle(cornerRadius: 16))
                                            Text(photo.caption.isEmpty ? "A little moment" : photo.caption).lineLimit(2)
                                            Label(photo.isActive ? "Showing" : "Hidden", systemImage: photo.isActive ? "display" : "eye.slash")
                                                .font(.caption).foregroundStyle(.secondary)
                                        }
                                    }.buttonStyle(.plain).accessibilityIdentifier("photo-\(photo.id)")
                                }
                            }
                        }
                    }
                }.padding(20)
            }.navigationTitle("Postcard").refreshable { await model.run { try await model.refresh() } }
            .sheet(item: $editing) { photo in PhotoEditor(model: model, photo: photo) }
            .onChange(of: picks) { _, values in
                guard !values.isEmpty else { return }
                captionFocused = false
                let viewerID = model.selectedID
                Task {
                    await model.run {
                        guard let viewerID, let api = model.api else { return }
                        var sent = 0
                        do {
                            for item in values {
                                model.progress = "Sending \(sent + 1) of \(values.count)…"
                                guard let data = try await item.loadTransferable(type: Data.self),
                                      let image = UIImage(data: data) else { throw PostcardError.server("Could not read this photo.") }
                                let jpeg = try jpegData(image)
                                try await api.upload(jpeg, viewerID: viewerID, caption: caption)
                                sent += 1
                                uploadMessage = "\(sent) of \(values.count) photos sent."
                            }
                            caption = ""
                        } catch {
                            try? await model.refresh()
                            throw PostcardError.server("\(sent) of \(values.count) photos sent. \(error.localizedDescription) Select remaining photos to retry.")
                        }
                        try await model.refresh()
                    }
                    picks = []
                }
            }
        }
    }
    func jpegData(_ image: UIImage) throws -> Data {
        let scale = min(1, 3840 / max(image.size.width, image.size.height))
        let size = CGSize(width: image.size.width * scale, height: image.size.height * scale)
        let format = UIGraphicsImageRendererFormat(); format.scale = 1
        let resized = UIGraphicsImageRenderer(size: size, format: format).image { _ in image.draw(in: CGRect(origin: .zero, size: size)) }
        guard let data = resized.jpegData(compressionQuality: 0.88) else { throw PostcardError.server("Could not prepare photo.") }
        return data
    }
    func send(_ images: [Data]) async {
        await model.run {
            guard let id = model.selectedID, let api = model.api else { return }
            for image in images { try await api.upload(image, viewerID: id, caption: caption) }
            uploadMessage = "\(images.count) photos sent."; caption = ""
            try await model.refresh()
        }
    }
}
